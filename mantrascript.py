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

USAGE
=====

- Change the configuration (resolution etc.) below
- Run this script
- Define one or more objects. Press Escape when to abort the object definition
  phase.
- Track your objects!
"""

import sys
from mantra import etracker
import os

# Some options
resolution = 320, 240
device = None # Get first device
mantra = None # No GUI
protocol = 'udp' # udp for OpenSesame, tcp for E-Prime
log_file = 'recording.tsv'

# Initialize the tracker
et = etracker.etracker(device, resolution, mantra)
et.comm_protocol = protocol
et.fname = log_file

# Keep adding new objects until escape is pressed
while True:
	o = et.define_object(0)
	if o == None:
		if len(et.objects) == 0:			
			print "Exiting"
			sys.exit()
		break
	print "Object has the following RGB values:", o.color
	et.objects.append(o)

# Track!
et.track_objects()

