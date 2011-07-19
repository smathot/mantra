"""
This file is part of Mantra.

Mantra is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Mantra is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Mantra.  If not, see <http://www.gnu.org/licenses/>.
"""

import pygame
import calibrate
from pygame.locals import *
import datetime
import math
import socket
import thread
import os
import pickle
from PIL import Image
from PIL import ImageDraw
from mantra import camera, v4l2_cid

class etracker:

	"""
	Etracker handles much of the actual tracking.
	Some of the tracking is also handled by camera, which is written in C and is therefore faster.
	"""	
 
	def __init__(self, camera_dev, resolution, mantra):
	
		"""
		Initialize the tracker
		"""					
		
		devices = self.available_camera_devices()
		
		if len(devices) == 0:
			print "No video devices (/dev/videoX) have been found!"
			quit(1)
		
		if camera_dev == None:
			self.camera_dev = devices[0]
		else:			
			self.camera_dev = camera_dev
			
		self.mantra = mantra
		
		if resolution == None:
			resolution = 640, 480
		
		camera.camera_init(self.camera_dev, resolution[0], resolution[1])

		self.resolution = camera.camera_get_width(), camera.camera_get_height()

		# These paths work at least on Ubuntu 9.10, but there is
		# probably a more clever way to find fonts. Anyway, if no
		# fonts are found, we just fall back to an ugly default font.
		self.font_list = [
			"/usr/share/fonts/truetype/ttf-dejavu/DejaVuSansMono.ttf",
			"/usr/share/fonts/truetype/ttf-liberation/LiberationMono-Regular.ttf",			
			"/usr/share/fonts/truetype/msttcorefonts/Andale_Mono.ttf",
			"/usr/share/fonts/truetype/freefont/FreeMono.ttf"
			]						
		
		# Set some default values
		self.host = ""
		self.port = 40007
		self.fname = "recording.tsv"
		self.comm_thread = None
		self.control_mouse = False
		self.log = None
		self.log_samples = True
		self.accuracy = 4								
		self.display_margin = 200
		self.monitor_webcam = False
		self.monitor_tracking = True
		self.predict = True
		self.smov_threshold = 20
		self.emov_threshold = 5
		self.v3d = False
		self.z_scale = 0.1
		self.tracking = False
		self.pause_tracking = False				
		self.font_size = 10
		self.line_spacing = 3
		self.comm_protocol = "tcp"
		self.sample_nr = 0
		self.last_comm_sample = -1
		self.target_t_res = 40

		self.objects = []
		
		# Initialize Pygame
		pygame.init()
		
	def close(self):
		
		"""
		Performs a graceful shutdown
		"""
		
		camera.camera_close()

	def bind_socket(self, protocol):

		"""
		Binds to a socket using a specified protocol
		"""

		self.sock = socket.socket(socket.AF_INET, protocol)
		bound = False
		while not bound:
			try:
				self.sock.bind( (self.host, self.port) )
				print "Listening on port", self.port
				bound = True
			except:
				print "Unable to bind to port", self.port
				self.port += 1

	def comm_send(self, s):

		"""
		Sends a single message
		"""
		
		if self.comm_protocol == "tcp":
			self.conn.send(s)
		else:
			self.sock.sendto(s, self.comm_addr)				

	def comm_process(self, s):

		"""
		Handles a single request and sends a reply if necessary
		"""
		
		# Only handle requests while tracking
		if self.tracking:

			# Make the string nice and readable
			s = s.strip().upper()

			# Split the request for easy processing
			data = s.split(" ")

			# Logs a message
			if data[0] == "LOG":
				try:
					self.log.write("%s\tMSG\t%s\n" % (pygame.time.get_ticks(), s[4:]))
				except:
					print "etracker.comm_process(): failed to write to logfile"					
				return True
	
			# Returns a sample
			if data[0] == "SAMP" and len(data) == 2:

				# Wait until a new sample is available
				while self.sample_nr == self.last_comm_sample:
					pygame.time.wait(5)
					
				i = int(data[1])
				if i < len(self.objects):
					o = self.objects[i]
					self.comm_send("%d %s %s %s\n" % (o.going, o.cpos[0], o.cpos[1], o.cpos[2]))
				else:
					self.comm_send("-1 -1 -1 -1\n")

				self.last_comm_sample = self.sample_nr
				return True
				
			# Returns a sample, but unlike the regular "SAMP"
			# it returns right away, without waiting for a new sample
			if data[0] == "NBSAMP" and len(data) == 2:
			
				i = int(data[1])
				if i < len(self.objects):
					o = self.objects[i]
					self.comm_send("%d %s %s %s\n" % (o.going, o.cpos[0], o.cpos[1], o.cpos[2]))
				else:
					self.comm_send("-1 -1 -1 -1\n")				
							
			# Waits for the start/ end of a movement
			if (data[0] == "SMOV" or data[0] == "EMOV") and len(data) == 2:
				i = int(data[1])
				if i < len(self.objects):
					self.objects[i].comm_wait = data[0]
				return True				
					
			# Say hi back (for communication testing purposes)
			if s == "HI":
				self.comm_send("HI\n")
				return True

			# The client says bye, so disconnect
			if s == "BYE":
				return False
				
			# Stop tracking
			if s == "STOP":
				self.stop_tracking = True
				return True
				
			# Use a specific file for logging
			if data[0] == "FILE" and len(data) == 2:
				self.fname = data[1]
				self.mantra.set_filename(self.fname)
				self.start_log()
				return True
				
			# Adds a calibration point
			if data[0] == "CPT" and len(data) == 8:
				i = int(data[1])
				if i < len(self.objects):
					o = self.objects[i]
					in_x = int(data[2])
					in_y = int(data[3])
					in_z = int(data[4])
					out_x = int(data[5])
					out_y = int(data[6])
					out_z = int(data[7])
				
					if o.calibration == None:
						o.calibration = calibrate.calibrate()
					o.calibration.pts.append( ( (in_x, in_y, in_z), (out_x, out_y, out_z) ) )
				return True
				
			# Performs the actual calibration
			if data[0] == "CAL" and len(data) == 2:
				i = int(data[1])
				if i < len(self.objects):
					o = self.objects[i]
					if o.calibration != None:
						o.calibration.calibrate()
				return True
					
			# Forgets the calibration
			if data[0] == "UCAL" and len(data) == 2:
				i = int(data[1])
				if i < len(self.objects):
					o = self.objects[i]
					o.calibration = None
				return True
					
			return True		

	def comm_tcp(self):

		"""
		This function is spawned as a thread and handles communications
		through TCP/IP. UDP is the preferred methode, but is not
		supported by E-prime
		"""

		print "etracker.comm_tcp(): communicating using TCP"

		# Create a TCP socket		
		self.bind_socket(socket.SOCK_STREAM)		

		# Loop infinitely, waiting for clients to connect
		while True:

			print "etracker.comm_tcp(): waiting for an incoming connection"

			# Wait for an incoming connection
			self.sock.listen(1)			
			print "etracker.comm_tcp(): incoming connection ... "			
			self.conn, self.comm_addr = self.sock.accept()

			print "etracker.comm_tcp(): connected by %s:%s" % self.comm_addr
			
			self.comm_tcp_session()
						
	def comm_tcp_session(self):
	
		"""
		Handles a single connection session
		"""
						
		while True:

			s = ""
			while s[-1:] != "\n":
				rcv = self.conn.recv(128)			
				if rcv == False or rcv == "":
					break
				s += rcv

			if not rcv or rcv == "":
				print "etracker.comm_tcp_session(): connection closed"
				self.conn.close()
				return

			# Split the line, just in case multiple commands were
			# sent at once and process them
			for _s in s.split("\n"):
				if not self.comm_process(_s):
					print "etracker.comm_tcp_session(): connection closed"
					self.conn.close()
					return						
		
	def comm_udp(self):
	
		"""
		This function is spawned as a thread and handles communications.
		Communication is through UDP.
		"""

		print "etracker.comm_udp(): communicating using UDP"

		# Create a socket and bind it to the first available port (starting from the preferred port)
		self.bind_socket(socket.SOCK_DGRAM)
		
		# Loop infinitely until the application is quit somewhere else
		while True:
				
			# Wait for an incoming request
			s, self.comm_addr = self.sock.recvfrom(128)
			
			# Process the request
			self.comm_process(s)
			
	def available_camera_devices(self):
		
		"""
		Provides a list of available camera devices
		"""
		
		# List the available video devices
		camera_devices = []
		for dev in 	os.listdir("/dev"):
			if dev[:5] == "video":
				camera_devices.insert(0, "/dev/%s" % dev)
		return camera_devices		
			
	def reinit_camera(self, camera_dev, resolution):
		
		"""
		Attempts to change the resolution to a specific value
		"""
				
		camera.camera_close()
		camera.camera_init(camera_dev, resolution[0], resolution[1])
		self.camera_dev = camera_dev		
		self.resolution = camera.camera_get_width(), camera.camera_get_height()
		

	def available_camera_options(self):

		"""
		Provides a list of options supported by the camera
		"""

		options = []
		for option in dir(v4l2_cid):
			val = eval("v4l2_cid.%s" % option)
			if type(val) == int and camera.camera_control_available(val) and option[9:] not in ["BASE", "USER_BASE"]:
				options.append(option[9:].capitalize())
				
		return options

	def set_camera_option(self, option, value):

		"""
		Changes a camera option (contrast etc.)
		"""

		camera.camera_set_control(eval("v4l2_cid.V4L2_CID_%s" % option.upper()), value)

	def get_camera_option(self, option):

		"""
		Retrieves a camera option (contrast etc.)
		"""		

		return camera.camera_get_control(eval("v4l2_cid.V4L2_CID_%s" % option.upper()))		
														
	def create_screen(self, title):
	
		"""
		Creates a basic screen and initializes a font
		"""
	
		window = pygame.display.set_mode( (self.resolution[0], self.resolution[1] + self.display_margin) )
		pygame.display.set_caption(title)
		screen = pygame.display.get_surface()

		font = None
		
		# Walks through all fonts and pick the first available font
		for fname in self.font_list:
			if os.path.exists(fname):
				font = pygame.font.Font(fname, self.font_size)
				break

		# If no fonts are found, fall back to the default font
		if font == None:
			font = pygame.font.Font(None, self.font_size)
		
		return screen, font				
						
	def start_log(self):
	
		"""
		This function initializes the log file
		"""
	
		# Close the log if open and reopen it right away (using a different file)
		# Make sure that no exception occurs if the log cannot be closed, because
		# it is currently being written to, but wait and try again.
		if self.log != None:
			closed = False
			while not closed:
				try:
					self.log.close()
					print "etracker.start_log(): successfully closed logfile"
					closed = True
				except:
					print "etracker.start_log(): failed to close logfile, retrying ..."
					pygame.time.wait(50)
							
		# Make sure that we don't overwrite the previous logfile by prepeding a "_"
		# to the logfile in case of an existing filename.
		fname_changed = False
		while os.path.exists(self.fname):
			fname_changed = True
			self.fname = "_" + self.fname
			print "etracker.start_log(): changing logfile to %s" % self.fname	
		if fname_changed:
			self.mantra.set_filename(self.fname)
		
		# Open the logfile
		self.log = open(self.fname, "w")

		# Log some initial information				
		self.log.write("%s\tFILENAME\t%s\n" % (pygame.time.get_ticks(), self.fname))
		self.log.write("%s\tDATETIME\t%s\n" % (pygame.time.get_ticks(), datetime.datetime.now().ctime()))		
		self.log.write("%s\tCAMERA_DEVICE\t%s\n" % (pygame.time.get_ticks(), self.camera_dev))
		self.log.write("%s\tRESOLUTION\t%d\t%d\n" % (pygame.time.get_ticks(), self.resolution[0], self.resolution[1]))
		
		self.log.write("%s\tMATCH_MODE\t%d\n" % (pygame.time.get_ticks(), camera.cvar.match_mode))						
		self.log.write("%s\tSIZE_MODE\t%d\n" % (pygame.time.get_ticks(), camera.cvar.size_mode))
		self.log.write("%s\tVELOCITY_3D\t%d\n" % (pygame.time.get_ticks(), self.v3d))
		self.log.write("%s\tLOG_SAMPLES\t%d\n" % (pygame.time.get_ticks(), self.log_samples))		
		self.log.write("%s\tCONTROL_MOUSE\t%d\n" % (pygame.time.get_ticks(), self.control_mouse))		
		
		if not self.monitor_tracking:
			self.log.write("%s\tMONITOR_MODE\tSILENT\n" % pygame.time.get_ticks())
		elif self.monitor_tracking and not self.monitor_webcam:
			self.log.write("%s\tMONITOR_MODE\tTRACKING\n" % pygame.time.get_ticks())
		else:
			self.log.write("%s\tMONITOR_MODE\tWEBCAM\n" % pygame.time.get_ticks())		
				
		for o in self.objects:		
			self.log.write("%s\tOBJECT\t%s\t%s\t%d\n" % (pygame.time.get_ticks(), o.name, o.color, o.fuzziness))								
			
	def define_object(self, object_id):
	
		"""
		This function provides an easy way to select the color and fuzziness for object tracking		
		"""

		screen, font = self.create_screen("Define Object")
		
		target_color = None
		fuzziness = 50

		# Loop until a key is pressed (which is handled in the loop)
		while True:		
										
			# Create a blank screen
			screen.fill( (0, 0, 0) )
			
			# Draw some text	
			text = font.render("Defining: %s" % object_id, False, (255, 255, 255))							
			screen.blit(text, (10, 10))			
			text = font.render("Press <Enter> to accept and <Escape> to cancel", False, (255, 255, 255))							
			screen.blit(text, (10, 30))			
			if target_color != None:
				text = font.render("Target color = %d, %d, %d" % target_color, False, target_color)			
			else:
				text = font.render("Click on the image to select a color", False, (255, 255, 255))					
			screen.blit(text, (10, 50))
			text = font.render("Fuzziness = %d <press 'up' or 'down' to change>" % fuzziness, False, (255, 255, 255))							
			screen.blit(text, (10, 70))
			text = font.render("Match mode = %d <'m'>" % camera.cvar.match_mode, False, (255, 255, 255))
			screen.blit(text, (10, 90))

			# Capture the image
			camera.camera_capture()
			
			# Make the matching part of the webcam image green
			if target_color != None:
				camera.highlight_color(target_color[0], target_color[1], target_color[2], fuzziness)

			# Display the image and the text				
			im = pygame.image.frombuffer(camera.camera_to_string(), self.resolution, "RGB")
			screen.blit(im, (0, self.display_margin))
									
			# Display the webcam image			
			pygame.display.flip()			
		
			# Process user input		
			for event in pygame.event.get()	:
				if event.type == KEYDOWN:
				
					# Quit and return an object
					if event.key == pygame.K_RETURN and color != None:
						pygame.display.quit()
						return tracker_object(object_id, target_color, fuzziness, self)
					
					# Quit without a color
					if event.key == pygame.K_ESCAPE:
						pygame.display.quit()
						return None
				
					# Change the match mode
					if event.key == pygame.K_m:
						camera.cvar.match_mode = 1 - camera.cvar.match_mode
						
					# Change fuzziness
					if event.key == pygame.K_DOWN:
						fuzziness -= 1
					if event.key == pygame.K_UP:
						fuzziness += 1					
					
				# Read a color from the image 
				if event.type == MOUSEBUTTONDOWN:											
					pos = pygame.mouse.get_pos()								
					if pos[1] >= self.display_margin:
						if target_color == None:
							camera.camera_get_px(pos[0], pos[1] - self.display_margin)
							target_color = camera.cvar.r, camera.cvar.g, camera.cvar.b
						else:
							target_color = None
												
						
	def track_objects(self):
	
		"""		
		This function performs the actual tracking
		"""
									
		# Spawn the communications thread. Since the thread remains active
		# if tracking is stopped, this is done only once
		if self.comm_thread == None:
			if self.comm_protocol.lower() == "udp":
				self.comm_thread = thread.start_new_thread(self.comm_udp, ())
			else:
				self.comm_thread = thread.start_new_thread(self.comm_tcp, ())
		self.comm_addr = None

		# Initialize the log
		self.start_log()
	
		# Initialize the screen
		screen, font = self.create_screen("Track objects")		
						
		# Keep tracking until tracking is set to stop
		self.tracking = True
		self.pause_tracking = False				
		t = pygame.time.get_ticks()
		
		while self.tracking:
		
			# Pause until pause_tracking is set to false
			if self.pause_tracking:			
				try:
					self.log.write("%s\tPAUSE\n" % pygame.time.get_ticks())			
				except:
					print "Failed to write to logfile"					
				text = font.render("Paused <press any key to resume>", False, (255, 255, 255))
				screen.blit(text, (10, self.display_margin + self.line_spacing))
				pygame.display.flip()
				while self.pause_tracking:
					pygame.time.wait(500)
					for event in pygame.event.get()	:
						if event.type == KEYDOWN:
							self.pause_tracking = False
				try:																							
					self.log.write("%s\tRESUME\n" % pygame.time.get_ticks())
				except:
					print "Failed to write to logfile"					

			# Delay
			delay = self.target_t_res - pygame.time.get_ticks() + t
			if delay > 0:				
				pygame.time.wait(delay)

			# Keep track of timing									
			t_res = pygame.time.get_ticks() - t
			t = pygame.time.get_ticks()		
	
			# Draw some information to the screen
			if self.monitor_tracking:
				screen.fill( (0, 0, 0) )
				pygame.draw.rect(screen, (255, 255, 255), (0, self.display_margin, self.resolution[0], self.resolution[1]), 1)
				text = font.render("%.3d ms (%.3d fps)" % (t_res, 1000/ t_res), False, (255, 255, 255))
				screen.blit(text, (self.resolution[0] - 100, 10))				
				text = font.render("Match mode: %d <'m'>  Size mode: %d <'i'>" % (camera.cvar.match_mode, camera.cvar.size_mode), False, (255, 255, 255))
				screen.blit(text, (10, 10))				
				text = font.render("3D velocity: %d <'v'> Log samples: %d <'l'> Control mouse: %d <'c'>" % (self.v3d, self.log_samples, self.control_mouse), False, (255, 255, 255))
				screen.blit(text, (10, 20))	
				text = font.render("Port %d (%s)" % (self.port, self.comm_protocol), False, (255, 255, 255))
				screen.blit(text, (self.resolution[0] - 100, 20))
								
			spacing = self.line_spacing * self.font_size

			# Capture the image			
			camera.camera_capture()

			t2 = pygame.time.get_ticks()
						
			# Walk through all objects
			for o in self.objects:					
								
				# Obtain the object position using camera
				camera.track_object(o.color[0], o.color[1], o.color[2], o.fuzziness, o.pre[0], o.pre[1], self.monitor_webcam)
				o.track( (camera.cvar.track_x, camera.cvar.track_y, camera.cvar.track_z), t, t_res)
				self.sample_nr += 1
											
				# If the webcam is monitored, overlay the image
				
				if self.monitor_webcam:
					im = pygame.image.frombuffer(camera.camera_to_string(), self.resolution, "RGB")	
					screen.blit(im, (0, self.display_margin))
																																
				# If the object was detected								
				if not o.lost:				
																								
					# Log the sample
					if self.log_samples:
						try:								
							self.log.write("%s\tSAMPLE\t%s\t%d\t%s\t%s\t%s\t%s\t%s\n" % ((t, o.name, o.going) + o.cpos + (o.v, o.a)))					
						except:
							print "Failed to write to logfile"
						
					# Control the mouse pointer
					if self.control_mouse:
						pygame.mouse.set_pos( (o.cpos[0], o.cpos[1]) )
					
					# Print information to the screen
					if self.monitor_tracking:																
					
						text = font.render(o.name, False, o.color)
						screen.blit(text, (10, 10 + spacing))																															
						pygame.draw.circle(screen, (255, 0, 0), (int(o.pos[0]), int(o.pos[1] + self.display_margin)), int(o.pos[2] * self.z_scale))
						pygame.draw.line(screen, (0, 255, 0), (o.pos[0], o.pos[1] + self.display_margin), (o.pre[0], o.pre[1] + self.display_margin))
						text = font.render(o.name, False, o.color)
						screen.blit(text, (o.pos[0], o.pos[1] + self.display_margin))															
						text = font.render("Real: (%.4d, %.4d, %.4d) V:%.2f A:%.2f" % (o.pos[0], o.pos[1], o.pos[2], o.v, o.a), False, (255, 255, 255))
						screen.blit(text, (100, 10 + spacing))												
						text = font.render("Calibrated: (%.4d, %.4d, %.4d)" % o.cpos, False, (255, 255, 255))
						screen.blit(text, (100, 20 + spacing))
									
						if o.going:
							text = font.render("MOVING", False, (0, 255, 0))				
							screen.blit(text, (self.resolution[0] - 100, 10 + spacing))
																
				else:
					# Log that the object was lost
					if self.log_samples:	
						try:
							self.log.write("%s\tLOST\t%s\n" % (t, o.name))
						except:
							print "Failed to write to logfile"
						
					if self.monitor_tracking:					
						text = font.render("Object lost", False, (255, 255, 255))							
						screen.blit(text, (100, 15 + spacing))
							
				spacing += int(self.line_spacing * self.font_size)
						
			# Process user input
			for event in pygame.event.get()	:
				if event.type == KEYDOWN:
				
					# Return walks through the monitor modes
					if event.key == pygame.K_RETURN:
						if not self.monitor_tracking:
							self.monitor_tracking = True
							try:
								self.log.write("%s\tMONITOR_MODE\tTRACKING\n" % pygame.time.get_ticks())
							except:
								print "Failed to write to logfile"
						elif self.monitor_tracking and not self.monitor_webcam:
							self.monitor_webcam = True
							try:
								self.log.write("%s\tMONITOR_MODE\tWEBCAM\n" % pygame.time.get_ticks())
							except:
								print "Failed to write to logfile"								
						else:
							self.monitor_tracking = False
							self.monitor_webcam = False
							try:
								self.log.write("%s\tMONITOR_MODE\tSILENT\n" % pygame.time.get_ticks())
							except:
								print "Failed to write to logfile"								
							screen.fill( (0, 0, 0) )
							text = font.render("Silent mode", False, (255, 255, 255))							
							screen.blit(text, (10, 10))						
							text = font.render("Press <Enter> to cycle between Silent, Monitor and Webcam mode", False, (255, 255, 255))							
							screen.blit(text, (10, 30))				
							pygame.display.flip()		
						
					# M changes the match mode
					if event.key == pygame.K_m:
						camera.cvar.match_mode = 1 - camera.cvar.match_mode
						try:
							self.log.write("%s\tMATCH_MODE\t%d\n" % (pygame.time.get_ticks(), camera.cvar.match_mode))
						except:
							print "Failed to write to logfile"							
												
					# I changes the size mode
					if event.key == pygame.K_i:
						camera.cvar.size_mode = 1 - camera.cvar.size_mode						
						try:
							self.log.write("%s\tSIZE_MODE\t%d\n" % (pygame.time.get_ticks(), camera.cvar.size_mode))
						except:
							print "Failed to write to logfile"							
						
					# V changes the velocity mode (whether or not it takes depth into account)
					if event.key == pygame.K_v:
						self.v3d = not self.v3d
						try:
							self.log.write("%s\tVELOCITY_3D\t%d\n" % (pygame.time.get_ticks(), self.v3d))
						except:
							print "Failed to write to logfile"							
						
					# L toggles whether or not samples are logged
					if event.key == pygame.K_l:
						self.log_samples = not self.log_samples
						try:
							self.log.write("%s\tLOG_SAMPLES\t%d\n" % (pygame.time.get_ticks(), self.log_samples))		
						except:
							print "Failed to write to logfile"							
						
					# C toggles mouse cursor control
					if event.key == pygame.K_c:
						self.control_mouse = not self.control_mouse													
						try:
							self.log.write("%s\tCONTROL_MOUSE\t%d\n" % (pygame.time.get_ticks(), self.control_mouse))
						except:
							print "Failed to write to logfile"							
												
					# Escape cancels tracking
					if event.key == pygame.K_ESCAPE:				
						self.tracking = False

					# P pauses tracking
					if event.key == pygame.K_p:																	
						self.pause_tracking = True
										
					# If a key is pressed, the options in the UI should be changed accordingly		
					self.mantra.set_options()

			# Flush the display
			if self.monitor_tracking:				
				pygame.display.flip()
					
		# Close the display and the log
		pygame.display.quit()
		self.log.close()
																		
class tracker_object:

	"""
	This class corresponds to an object used for tracking.
	It also handles estimation of movement, velocity, etc.
	"""

	def __init__(self, name, color, fuzziness, et):
	
		"""
		Initialize the object using some default values
		"""
	
		self.name = name
		self.color = color
		self.fuzziness = fuzziness
		self.calibration = None
		self.et = et
		
		self.lost = True
		self.pv = 0
		self.v = 0
		self.a = 0
		self.pos = 320, 240, 100
		self.cpos = 320, 240, 100
		self.pre = 320, 240, 100
		self.going = False
		self.start_pos = 0, 0, 0
		self.end_pos = 0, 0, 0
		self.comm_wait = None
		
		self.c = []
		
	def track(self, pos, t, t_res):
	
		"""
		Update the position, predicted position, movement status etc.
		"""
	
		# Determine whether the object was found
		if pos[2] > 0:
				
			self.lost = False
			dx = pos[0] - self.pos[0]
			dy = pos[1] - self.pos[1]
			dz = pos[2] - self.pos[2]
		
			# Determine the velocity
			if self.et.v3d:
				v = math.sqrt( dx ** 2 + dy ** 2 + dz ** 2)		
			else:
				v = math.sqrt( dx ** 2 + dy ** 2)	
			
			# Acceleration
			self.a = (v - self.v) / t_res
			self.v = v				
			self.pos = pos
			
			# Predicted position for the next sample
			self.pre = int(pos[0] + dx), int(pos[1] + dy), int(pos[2] + dz)
		
			# Get calibrated coordinates (if specified)
			if self.calibration == None:
				self.cpos = self.pos
			else:
				self.cpos = self.calibration.estimate(self.pos)
		
			# Determine movement start
			if self.v > self.et.smov_threshold and not self.going:					
				self.going = True
				self.start_pos = self.cpos
				try:
					self.et.log.write("%s\tMOVEMENT_START\t%s\t%s\t%s\t%s\n" % ((t, self.name) + self.start_pos))
				except:
					print "Failed to write to logfile"					
			
				if self.comm_wait == "SMOV":
					self.et.comm_send("%s %s %s\n" % self.start_pos)
					self.comm_wait = None
							
			# Determine movement end
			if self.v < self.et.emov_threshold and self.going:
				self.going = False
				self.end_pos = self.cpos
				try:
					self.et.log.write("%s\tMOVEMENT_END\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % ((t, self.name) + self.start_pos + self.end_pos))
				except:
					print "Failed to write to logfile"					
			
				if self.comm_wait == "EMOV":
					self.et.comm_send("%s %s %s %s %s %s\n" % (self.start_pos + self.end_pos))
					self.comm_wait = None
					
		# If the object was lost, do not update
		else:
			self.lost = True
	
