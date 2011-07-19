#!/usr/bin/env python
#-*- coding:utf-8 -*-

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

from PyQt4 import QtCore, QtGui
import sys
import os
import os.path
import pickle
from mantra import etracker, about_gui, mantra_gui, v4l2_cid, camera
import thread		

class qtmantra(QtGui.QMainWindow):

	"""
	Mantra is the GUI which controls Etracker, which handles the actual tracking
	"""
	
	version = "0.41"
	
	def __init__(self, parent = None):
	
		"""
		The constructor
		"""
		
		QtGui.QWidget.__init__(self, parent)
												
		# Setup the UI
		self.ui = mantra_gui.Ui_MainWindow()
		self.ui.setupUi(self)
		self.toggle_advanced_options()
		self.toggle_camera_options()
		
		self.ui.title.setText(str(self.ui.title.text()).replace("[version]", self.version))
		self.setWindowTitle("Mantra %s" % self.version)
		
		# Restore settings and init with default values if this fails
		if not self.restore_settings(os.environ["HOME"] + "/.default.mantraprofile"):		
			self.et = etracker.etracker(None, None, self)
		
		# Continu setting up the UI
		self.set_options()	
		self.timer = QtCore.QTimer()
		
		# Make the connections
		QtCore.QObject.connect(self.ui.actionAdd_object, QtCore.SIGNAL("triggered()"), self.define_object)
		QtCore.QObject.connect(self.ui.actionClear_objects, QtCore.SIGNAL("triggered()"), self.clear_objects)
		QtCore.QObject.connect(self.ui.actionStart, QtCore.SIGNAL("triggered()"), self.start_tracking)
		QtCore.QObject.connect(self.ui.actionStop, QtCore.SIGNAL("triggered()"), self.stop_tracking)
		QtCore.QObject.connect(self.ui.actionPause, QtCore.SIGNAL("triggered()"), self.pause_tracking)
		QtCore.QObject.connect(self.ui.actionAbout, QtCore.SIGNAL("triggered()"), self.about_dialog)
		QtCore.QObject.connect(self.ui.actionQuit, QtCore.SIGNAL("triggered()"), self.close)
		QtCore.QObject.connect(self.ui.actionSave_profile, QtCore.SIGNAL("triggered()"), self.save_profile)
		QtCore.QObject.connect(self.ui.actionOpen_profile, QtCore.SIGNAL("triggered()"), self.open_profile)

		QtCore.QObject.connect(self.ui.actionShow_advanced_options, QtCore.SIGNAL("triggered()"), self.toggle_advanced_options)
		QtCore.QObject.connect(self.ui.actionShow_camera_options, QtCore.SIGNAL("triggered()"), self.toggle_camera_options)
		
		QtCore.QObject.connect(self.ui.button_browse, QtCore.SIGNAL("clicked()"), self.browse)
		QtCore.QObject.connect(self.ui.button_change_resolution, QtCore.SIGNAL("clicked()"), self.change_resolution)
		QtCore.QObject.connect(self.ui.button_change_camera, QtCore.SIGNAL("clicked()"), self.change_camera)
		
		QtCore.QObject.connect(self.ui.spinbox_smov_threshold, QtCore.SIGNAL("valueChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.spinbox_emov_threshold, QtCore.SIGNAL("valueChanged(int)"), self.option_changed)		
		QtCore.QObject.connect(self.ui.spinbox_min_z, QtCore.SIGNAL("valueChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.spinbox_framerate, QtCore.SIGNAL("valueChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.checkbox_log_samples, QtCore.SIGNAL("stateChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.checkbox_v3d, QtCore.SIGNAL("stateChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.checkbox_monitor_tracking, QtCore.SIGNAL("stateChanged(int)"), self.option_changed)						
		QtCore.QObject.connect(self.ui.checkbox_monitor_webcam, QtCore.SIGNAL("stateChanged(int)"), self.option_changed)		
		QtCore.QObject.connect(self.ui.checkbox_control_mouse, QtCore.SIGNAL("stateChanged(int)"), self.option_changed)		
		QtCore.QObject.connect(self.ui.combobox_match_mode, QtCore.SIGNAL("currentIndexChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.combobox_size_mode, QtCore.SIGNAL("currentIndexChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.combobox_comm_protocol, QtCore.SIGNAL("currentIndexChanged(int)"), self.option_changed)
		QtCore.QObject.connect(self.ui.edit_host, QtCore.SIGNAL("editingFinished()"), self.option_changed)
		QtCore.QObject.connect(self.ui.spinbox_port, QtCore.SIGNAL("valueChanged(int)"), self.option_changed)

		#self.et.objects.append(etracker.tracker_object("MARKER", (255, 91, 120), 50, self.et))

		self.populate_camera_options()										
		
	def closeEvent(self, event):
		
		"""
		Close, but save settings first
		"""
		
		self.save_settings(os.environ["HOME"] + "/.default.mantraprofile")
		self.et.close()
		event.accept()

	def change_resolution(self):

		"""
		Changes the resolution
		"""
		if self.ui.label_status.text() == "idle":
			s_resolution, accepted = QtGui.QInputDialog.getText(self, "Choose resolution", "Please enter a valid resolution (e.g. '640x480')")
			if accepted:
				try:
					resolution = int(s_resolution.split("x")[0]), int(s_resolution.split("x")[1])
				except:
					QtGui.QMessageBox.information(self, "Invalid resolution", "A resolution must consist of two x-separated numbers, such as '640x480'")
					return
				self.et.reinit_camera(self.et.camera_dev, resolution)			
				self.set_options()				
		else:
			QtGui.QMessageBox.information(self, "Status not idle", "You can only change the camera resolution when the camera is not in use.")				
				
	def change_camera(self):
	
		"""
		Changes the camera device
		"""

		if self.ui.label_status.text() == "idle":
			camera_devices = self.et.available_camera_devices()										
			camera_device, accepted = QtGui.QInputDialog.getItem(self, "Choose camera", "Which camera device do you want to use?", camera_devices)		
			if accepted:	
				self.et.reinit_camera(str(camera_device), self.et.resolution)
				self.populate_camera_options()				
				self.set_options()
		else:
			QtGui.QMessageBox.information(self, "Status not idle", "You can only change the camera device when the camera is not in use.")			

	def populate_camera_options(self):

		"""
		Queries the camera for available options and generates
		input based on these options.
		"""
		
		# Hide the existing options (if any)
		if hasattr(self, "widget_list_camera_options"):
			for w in self.widget_list_camera_options:
				w.hide()

		# Make a list of available camera options
		self.spinbox_list_camera_options = []
		self.widget_list_camera_options = []				
		for option in self.et.available_camera_options():

			w = QtGui.QWidget(self.ui.scrollarea_camera_contents)
			l = QtGui.QHBoxLayout(w)
			w.setLayout(l)

			label = QtGui.QLabel(option)
			l.addWidget(label)
			
			val = self.et.get_camera_option(option)			
			
			spinbox = QtGui.QSpinBox()
			spinbox.setRange(-10000, 10000)
			spinbox.setValue(val)
			spinbox.oldValue = val
			spinbox.option = option
			l.addWidget(spinbox)

			QtCore.QObject.connect(spinbox, QtCore.SIGNAL("valueChanged(int)"), self.set_camera_options)
			self.spinbox_list_camera_options.append(spinbox)
			self.widget_list_camera_options.append(w)
			
			self.ui.layout_camera_options.addWidget(w)

	def set_camera_options(self):

		"""
		Sends changed camera options to the camera
		"""		

		for spinbox in self.spinbox_list_camera_options:												
			
			if spinbox.oldValue != spinbox.value():			
				self.et.set_camera_option(spinbox.option, spinbox.value())
				val = self.et.get_camera_option(spinbox.option)
				spinbox.setValue(val)
				spinbox.oldValue = val				
		
						
	def get_camera_nr(self):
	
		"""
		Retrieves the camera nr from the UI
		"""
	
		return self.ui.spinbox_camera_nr.value()
		
	def set_camera_nr(self, camera_nr):
	
		"""
		Sets the UI camera nr
		"""
	
		self.ui.spinbox_camera_nr.setValue(camera_nr)
		
	def get_filename(self):
	
		"""
		Retrieves the filename from the UI
		"""
	
		return str(self.ui.edit_file.text())
		
	def set_filename(self, fname):
	
		"""
		Sets the UI filename.
		Also sets the filename in Etracker
		"""
	
		self.ui.edit_file.setText(fname)
		self.et.fname = str(fname)
		
	def set_status(self, msg):
	
		"""
		Sets the status message
		"""
	
		self.ui.label_status.setText(msg)
		
	def browse(self):
	
		"""
		Presents a file chooser for the filename
		"""
	
		fname = QtGui.QFileDialog.getOpenFileName(self, "Select a file for recording", ".")
		if fname != "":
			self.set_filename(fname)		
		
	def toggle_advanced_options(self):
	
		"""
		Toggles the visibility of the advanced options
		"""

		if not self.ui.actionShow_advanced_options.isChecked():
			self.ui.dock_advanced_options.close()
		else:
			self.ui.dock_advanced_options.show()
			
		self.adjustSize()

	def toggle_camera_options(self):

		"""
		Toggles the visibility of the camera options
		"""

		if not self.ui.actionShow_camera_options.isChecked():
			self.ui.dock_camera_options.close()
		else:
			self.ui.dock_camera_options.show()
			
		self.adjustSize()
									
	def option_changed(self, dummy = None):
	
		"""
		Synchronizes all options from the UI to Etracker
		"""
	
		self.et.log_samples = self.ui.checkbox_log_samples.isChecked()
		self.et.smov_threshold = self.ui.spinbox_smov_threshold.value()
		self.et.emov_threshold = self.ui.spinbox_emov_threshold.value()
		self.et.v3d = self.ui.checkbox_v3d.isChecked()
		self.et.monitor_tracking = self.ui.checkbox_monitor_tracking.isChecked()
		self.et.monitor_webcam = self.ui.checkbox_monitor_webcam.isChecked()
		etracker.camera.cvar.match_mode = self.ui.combobox_match_mode.currentIndex()
		etracker.camera.cvar.size_mode = self.ui.combobox_size_mode.currentIndex()
		etracker.camera.cvar.min_z = self.ui.spinbox_min_z.value()
		self.et.control_mouse = self.ui.checkbox_control_mouse.isChecked()
		self.et.host = str(self.ui.edit_host.text())
		self.et.port = self.ui.spinbox_port.value()
		self.et.target_t_res = 1000 / self.ui.spinbox_framerate.value()

		if self.ui.combobox_comm_protocol.currentIndex() == 0:
			self.et.comm_protocol = "tcp"
		else:
			self.et.comm_protocol = "udp"
		
	def set_options	(self):
	
		"""
		Synchronizes all option from Etracker to the UI
		"""
	
		self.ui.edit_resolution.setText("%d x %d" % self.et.resolution)
		self.ui.edit_camera_dev.setText(self.et.camera_dev)
		
		self.ui.checkbox_log_samples.setChecked(self.et.log_samples)
		self.ui.spinbox_smov_threshold.setValue(self.et.smov_threshold)
		self.ui.spinbox_emov_threshold.setValue(self.et.emov_threshold)		
		self.ui.checkbox_v3d.setChecked(self.et.v3d)
		self.ui.checkbox_monitor_tracking.setChecked(self.et.monitor_tracking)
		self.ui.checkbox_monitor_webcam.setChecked(self.et.monitor_webcam)
		self.ui.combobox_match_mode.setCurrentIndex(etracker.camera.cvar.match_mode)
		self.ui.combobox_size_mode.setCurrentIndex(etracker.camera.cvar.size_mode)
		self.ui.spinbox_min_z.setValue(etracker.camera.cvar.min_z)
		self.ui.checkbox_control_mouse.setChecked(self.et.control_mouse)	
		self.ui.edit_host.setText(self.et.host)			
		self.ui.spinbox_port.setValue(self.et.port)

		self.ui.spinbox_framerate.setValue(1000 / self.et.target_t_res)

		if self.et.comm_protocol == "tcp":
			self.ui.combobox_comm_protocol.setCurrentIndex(0)
		else:
			self.ui.combobox_comm_protocol.setCurrentIndex(1)
			
	def restore_settings(self, fname):
		
		"""
		Restores all settings from a file
		"""
		
		if not os.path.exists(fname):
			print "%s not found" % fname
			return False
		
		print "Restoring from %s" % fname
			
		f = open(fname, "r")
		try:
			settings = pickle.load(f)
		except:
			f.close()
			print "Failed to restore from %s" % fname
			return False
		f.close()
		
		camera_dev = settings["camera_dev"]
		resolution = settings["resolution"]
		
		# Initialize if etracker has not yet been initialized, reinit otherwise
		if hasattr(self, "et"):
			self.et.reinit_camera(camera_dev, resolution)
		else:
			self.et = self.et = etracker.etracker(camera_dev, resolution, self)

		self.et.log_samples = settings["log_samples"]
		self.et.smov_threshold = settings["smov_threshold"]
		self.et.emov_threshold = settings["emov_threshold"]
		self.et.v3d = settings["v3d"]
		self.et.monitor_tracking = settings["monitor_tracking"]
		self.et.monitor_webcam = settings["monitor_webcam"]
		etracker.camera.cvar.match_mode = settings["match_mode"]
		etracker.camera.cvar.size_mode = settings["size_mode"]
		etracker.camera.cvar.min_z = settings["min_z"]
		self.et.control_mouse = settings["control_mouse"]
		self.et.host = settings["host"]
		self.et.port = settings["port"]
		self.et.target_t_res = settings["target_tres"]
		self.et.comm_protocol = settings["protocol"]
		
		for option in settings["camera_options"]:
			self.et.set_camera_option(option, settings["camera_options"][option])
			
		for o in settings["objects"]:
			self.et.objects.append(etracker.tracker_object(o, settings["objects"][o][0], settings["objects"][o][1], self.et))
		self.update_object_list()
		
		return True
					
	def save_settings(self, fname):
		
		"""
		Saves all settings to a file
		"""
		
		print "Saving to %s" % fname
		
		settings = {}
		settings["camera_dev"] = self.et.camera_dev
		settings["resolution"] = self.et.resolution
		
		settings["log_samples"] = self.et.log_samples
		settings["smov_threshold"] = self.et.smov_threshold
		settings["emov_threshold"] = self.et.emov_threshold		
		settings["v3d"] = self.et.v3d
		settings["monitor_tracking"] = self.et.monitor_tracking
		settings["monitor_webcam"] = self.et.monitor_webcam
		settings["match_mode"] = etracker.camera.cvar.match_mode
		settings["size_mode"] = etracker.camera.cvar.size_mode
		settings["min_z"] = etracker.camera.cvar.min_z
		settings["control_mouse"] = self.et.control_mouse
		settings["host"] = self.et.host	
		settings["port"] = self.et.port
		settings["target_tres"] = self.et.target_t_res
		settings["protocol"] = self.et.comm_protocol
		
		camera_options = {}
		for spinbox in self.spinbox_list_camera_options:
			camera_options[spinbox.option] = spinbox.value()		
		settings["camera_options"] = camera_options
		
		objects = {}
		for o in self.et.objects:
			objects[o.name] = o.color, o.fuzziness
		settings["objects"] = objects			
		
		f = open(fname, "w")
		pickle.dump(settings, f)
		f.close()
		
	def open_profile(self):
		
		"""
		Provides a file chooser to open a profile
		"""
		
		fname = QtGui.QFileDialog.getOpenFileName(self, "Select a file containing a Mantra profile", ".", "*.mantraprofile")
		if fname != "":
			self.restore_settings(fname)
			
	def save_profile(self):
		
		"""
		Provides a file chooser to save a profile		
		"""
		
		fname = QtGui.QFileDialog.getSaveFileName(self, "Select a file containing a Mantra profile", ".", "*.mantraprofile")
		if fname != "":
			if fname[-14:] != ".mantraprofile":
				fname += ".mantraprofile"
			self.save_settings(fname)
			
	def update_object_list(self):
		
		"""
		Updates the list of objects in the gui
		"""
		
		if len(self.et.objects) > 0:
			l = []			
			for o in self.et.objects:
				l.append("%s\tfuzziness: %d\tcolor: %s" % (o.name, o.fuzziness, o.color))		
			self.ui.label_objects.setText("<br />".join(l))
		else:
			self.ui.label_objects.setText("No objects have been defined")
				
	def _define_object(self):
	
		"""
		Calls Etracker for object definition
		"""
	
		self.set_status("defining object")
		o = self.et.define_object("OBJECT_%d" % len(self.et.objects))		
		if o != None:
			self.et.objects.append(o)
			self.update_object_list()
			
		self.set_status("idle")
		
	def _start_tracking(self):
	
		"""
		Calls Etracker for tracking
		"""
	
		self.set_status("tracking")				
		self.et.track_objects()
		self.set_status("idle")	
		
	def start_tracking(self):
	
		"""
		A wrapper function which spawns _start_tracking() as a thread
		"""
	
		if len(self.et.objects) == 0:
			QtGui.QMessageBox.information(self, "Nothing to track", "Please define at least one object!")
			return		
	
		if self.ui.label_status.text() == "idle":
			thread.start_new_thread(self._start_tracking, ())
			
	def pause_tracking(self):
	
		"""
		Tells Etracker to pause tracking
		"""
	
		self.et.pause_tracking = not self.et.pause_tracking
		
	def stop_tracking(self):
	
		"""
		Tells Etracker to stop tracking
		"""
	
		self.et.tracking = False
		
				
	def define_object(self):
	
		"""
		A wrapper function which spwans _define_object() as a thread
		"""
	
		if self.ui.label_status.text() == "idle":
			thread.start_new_thread(self._define_object, ())
		
	def clear_objects(self):
	
		"""
		Tells Etracker to forget all objects and updates the UI
		"""
	
		if self.ui.label_status.text() == "idle":
			self.et.objects = []
			self.update_object_list()
			
			
	def about_dialog(self):
	
		"""
		Presents a simple about dialog
		"""
	
		a = QtGui.QDialog(self)		
		a.ui = about_gui.Ui_Dialog()
		a.ui.setupUi(a)	
		a.ui.title.setText(str(a.ui.title.text()).replace("[version]", self.version))
		a.adjustSize()
		a.show()				



