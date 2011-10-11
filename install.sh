#!/bin/bash

echo
echo "Mantra 0.41  Copyright (C) 2010-2011  Sebastiaan Mathôt"
echo
echo "This program comes with ABSOLUTELY NO WARRANTY"
echo "This is free software, and you are welcome to redistribute it"
echo "under certain conditions"
echo
echo "This script will install Mantra"
echo "Installation requires root access"
echo "For more installation please refer to the README file or consult"
echo "the website <http://www.cogsci.nl/mantra>"
echo
echo "Do you wish to continue? (y/N)"

if [ -d /usr/include/python2.7 ]
then
	PYPATH='/usr/include/python2.7'
elif [ -d /usr/include/python2.6 ]
then
	PYPATH='/usr/include/python2.6'
else
	echo "Failed to determine the correct Python path! Not installing"
	exit
fi

read response
if [ $response != "y" ]
then
	echo "Not installing..."
	exit
fi


if [ $# == 1 ] && [ $1 == "with_gui" ]
then
	echo "Compiling Qt Gui..."
	pyuic4 mantra/resources/mantra_gui.ui > mantra/mantra_gui.py
	pyuic4 mantra/resources/about_gui.ui > mantra/about_gui.py
	pyrcc4 mantra/resources/mantra.qrc > mantra/mantra_rc.py
fi

echo "Running SWIG..."

swig -python ./mantra/camera.i

if [ $? == 1 ]; then
	echo "Error while running SWIG"
	exit
fi

echo "Compiling camera..."

gcc -O2 -fPIC -c ./mantra/camera.c -I$PYPATH -L/usr/lib -lv4l2 -o ./mantra/camera.o

if [ $? == 1 ]; then
	echo "Error compiling camera.c"
	exit
fi

echo "Compiling camera_wrap..."

gcc -O2 -fPIC -c ./mantra/camera_wrap.c -I$PYPATH -I/usr/include/opencv -L/usr/lib -lv4l2 -o ./mantra/camera_wrap.o

if [ $? == 1 ]; then
	echo "Error compiling camera_wrap.c"
	exit
fi

echo "Linking.."

gcc -shared ./mantra/camera.o ./mantra/camera_wrap.o -o ./mantra/_camera.so -I/usr/include/opencv -L/usr/lib -lv4l2

if [ $? == 1 ]; then
	echo "Error linking"
	exit
fi

echo "Compilation complete!"
echo
echo "Please Enter your password to complete installation of Mantra:"
echo
python setup.py install
if [ $? == 1 ]; then
	echo "Error installing"
	echo "Did you run this script as root? (you should)"
	exit
fi
echo
echo "Installation complete! You can start Mantra using the following command:"
echo
echo "qtmantra"
echo

