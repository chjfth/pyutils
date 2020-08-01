#!/usr/bin/env python3
# coding: utf-8

import os, sys
import shutil
import configparser # ini operation
from . import share

def ReadIniItem(ini_filepath, section, itemname):
	iniobj = configparser.ConfigParser()
	iniobj.read(ini_filepath) # no matter if file not exist

	retpath = ""
	try:
		retpath = iniobj[section][itemname]
	except KeyError:
		retpath = ""
	return retpath

def WriteIniItem(ini_filepath, section, itemname, itemval):
	iniobj = configparser.ConfigParser()
	iniobj.read(ini_filepath) # no matter if file not exist

	try:
		_ = iniobj[section]
	except KeyError:
		iniobj[section] = {} # create an empty section

	iniobj[section][itemname] = itemval

	with open(ini_filepath, 'w') as inifile:
		iniobj.write(inifile)


def Seconds_to_DHM(seconds):
	minutes = seconds//60
	hours = minutes//60
	days = hours//24
	return (days, hours%24, minutes%60)

def RemoveDir_IfEmpty(dirpath):
	dir_parent = os.path.dirname(dirpath)
	files = os.listdir(dir_parent)
	if len(files)==0:
		os.rmdir(dir_parent)


if __name__=='__main__':
	inifp = 'irsync.ini'
	ret = ReadIniItem(inifp, 'last_success_dirpath', '192.168.11.1~1873.shelf1')
	WriteIniItem(inifp, 'sect1', 'item1', 'value10')
	WriteIniItem(inifp, 'sect1', 'item2', 'value20')
	ret = ReadIniItem(inifp, 'sect1', 'item2')
	pass