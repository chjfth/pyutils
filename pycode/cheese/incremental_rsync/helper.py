#!/usr/bin/env python3
# coding: utf-8

import os, sys, time
import shutil
import configparser # ini operation
# from .share import

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

def DHMS_to_Seconds(days, hours, minutes, seconds=0):
	total_seconds = ((days * 24 + hours) * 60 + minutes) * 60 + seconds
	return total_seconds

def Seconds_to_DHMS(total_seconds):
	minutes = total_seconds//60
	hours = minutes//60
	days = hours//24
	return (days, hours%24, minutes%60, total_seconds%60)

def RemoveDir_IfEmpty(dirpath):
	dir_parent = os.path.dirname(dirpath)
	files = os.listdir(dir_parent)
	if len(files)==0:
		os.rmdir(dir_parent)

def uesec_now():
	return int(time.time())

if __name__=='__main__':
	inifp = 'irsync.ini'
	ret = ReadIniItem(inifp, 'last_success_dirpath', '192.168.11.1~1873.shelf1')
	WriteIniItem(inifp, 'sect1', 'item1', 'value10')
	WriteIniItem(inifp, 'sect1', 'item2', 'value20')
	ret = ReadIniItem(inifp, 'sect1', 'item2')


