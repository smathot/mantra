#!/usr/bin/env python

from distutils.core import setup
import glob

setup(name='mantra',
	version='0.41',
	description='Camera based object tracking',
	author='Sebastiaan Mathot',
	author_email='s.mathot@cogsci.nl',
	url='http://www.cogsci.nl/mantra',
	scripts=['qtmantra'],	      
	packages=['mantra'],
	package_dir={'mantra' : 'mantra'},
	package_data={'mantra' : ['resources/icons/*.png', '*.c', '*.o', '*.so']},
	data_files=[
		('share/applications', ['data/mantra.desktop']),
		('share/pixmaps', ['data/icons/32x32/apps/mantra.png']),
		('share/icons/hicolor/scalable/apps', glob.glob('data/icons/scalable/apps/*.svg')),
		('share/icons/hicolor/16x16/apps', glob.glob('data/icons/16x16/apps/*.png')),
		('share/icons/hicolor/22x22/apps', glob.glob('data/icons/22x22/apps/*.png')),
		('share/icons/hicolor/24x24/apps', glob.glob('data/icons/24x24/apps/*.png')),
		('share/icons/hicolor/32x32/apps', glob.glob('data/icons/32x32/apps/*.png')),
		]
	)
