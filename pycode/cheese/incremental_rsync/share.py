#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, sys, time, subprocess
import math
import re
import datetime
import shlex
import glob
from enum import Enum,IntEnum # since Python 3.4
from .helper import *
from cheese.subprocess_tools import pipe_process_with_timeout

class MsgLevel(IntEnum):
	err = 1
	warn = 2
	info = 3
	dbg = 4

def print_nolf(msg):
	print(msg, end='')

class Err_irsync(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg

class Err_rsync_exec(Err_irsync):
	def __init__(self, exitcode, ushelf, extra_msg=""):
		errmsg = "rsync execution error, exitcode=%d. (ushelf=%s)"%(exitcode, ushelf)
		if extra_msg:
			errmsg += " " + extra_msg
		super().__init__(errmsg)
	

class err_FileExists(Exception): # internal use
	def __init__(self, errfilepath):
		self.errfilepath = errfilepath

def glueup_shell_cmd(argv_list):
	shell_cmd = ' '.join([shlex.quote(onearg) for onearg in argv_list])
	return shell_cmd

def datetime_str_by_uesec(uesec, msec=False, compact=False):
	tmlocal = time.localtime(uesec)
	if compact:
		timestr = time.strftime('%Y%m%d.%H%M%S', tmlocal)
	else:
		timestr = time.strftime('%Y-%m-%d_%H:%M:%S', tmlocal)

	if msec==True: # need milliseconds part
		msec_part = int( (uesec - math.floor(uesec))*1000%1000 )
		timestr += ".%03d"%(msec_part)

	return timestr

def datetime_str_now(msec=False, compact=False):
	uesec = time.time()
	return datetime_str_by_uesec(uesec, msec, compact)

def datetime_str_now___set_aside():
	now = datetime.datetime.now()
	timestr = "%04d%02d%02d.%02d%02d%02d.%03d"%(now.year, now.month, now.day, 
		now.hour, now.minute, now.second, now.microsecond/1000)
	return timestr

def datetime_by_pattern(pattern):
	# Example: pattern="YYYYMMDD.hhmmss"
	# Return: "20200411.153300"
	
	now = datetime.datetime.now()
	
	dt = pattern
	dt = dt.replace("YYYY", "%04d"%(now.year))
	dt = dt.replace("MM", "%02d"%(now.month))
	dt = dt.replace("DD", "%02d"%(now.day))
	dt = dt.replace("hh", "%02d"%(now.hour))
	dt = dt.replace("mm", "%02d"%(now.minute)) # use lower-case mm so not to conflict with Month
	dt = dt.replace("ss", "%02d"%(now.second))
	return dt

def _create_logfile_with_seq_once(filepath_pattern):
	
	# Example: filepath_pattern = "/rootdir/run*.log"
	# Result: "/rootdir/run1.log" or "/rootdir/run2.log" ... will be created.
	# If FileExistsError is raised, the caller should try calling it again.
	
	dirpath, filename_pattern = os.path.split(filepath_pattern)
	
	if not (filename_pattern.count('*')==1 and dirpath.count('*')==0):
		raise Err_irsync("BUG: filepath_pattern MUST contain one and only one '*'. Your filepath_pattern is '%s'."%(filepath_pattern))
	
	glob1, glob2 = filepath_pattern.split('*')
	globbing_pattern = glob.escape(glob1) + '*' + glob.escape(glob2)
	
	existings = glob.glob(globbing_pattern)
	
#	print("### (%s) %s"%(globbing_pattern,existings))
	if not existings:
		create_filename = filename_pattern.replace('*', '0')
	else:
		num_largest = 0
		sub1, sub2 = filename_pattern.split('*')
			# sub1="run", sub2=".log"
		
		for filepath in existings:
			filename = os.path.basename(filepath)
			""" 
Tip to remove starting "log" and ending "log" only once:
>>> "log.1.abc.2.log.3.log".split("log", 1)[1]
'.1.abc.2.log.3.log'
>>> "log.1.abc.2.log.3.log".rsplit("log", 1)[0]
'log.1.abc.2.log.3.'
"""
			core = filename.split(sub1, 1)[1]
			core = core.rsplit(sub2, 1)[0]
			
			# if core is a number string, save it for examination
			try:
				num = int(core)
			except ValueError:
				continue
			
			if num>num_largest:
				num_largest = num
		
		create_filename = "%s%d%s"%(sub1, num_largest+1, sub2)
	
	create_filepath = os.path.join(dirpath, create_filename)
	create_dirpath = os.path.dirname(create_filepath)
	
	if not os.path.exists(create_dirpath):
		os.makedirs(create_dirpath)
	
	try:
		fh = open(create_filepath, "x+") # typical: FileExistsError
	except FileExistsError:
		raise err_FileExists(create_filepath)
	
	return create_filepath, fh


_FileExists_max_retry = 10
#
def create_logfile_with_seq(filepath_pattern):
	"""
	filepath_pattern should have a single '*' in it, e.g. "20200412.run*.log"
	Return: tuple ( created_filepath , file_handle )
	
	Example: 
	filepath_pattern = "run*.log"
	Will try to create new file "run1.log", "run2.log", "run3.log" ... "run15.log" ...
	The actual number will be the greatest among all existing filenames(even though there is hole).
	"""
	
	filepaths = []
	for i in range(_FileExists_max_retry):
		try:
			return _create_logfile_with_seq_once(filepath_pattern)
		except err_FileExists as e:
			filepaths.append( e.errfilepath )
			continue
	
	# Report error below:
	text  = "Creating a log file with pattern, fail unexpectedly with FileExistsError.\n"
	text += "Log file pattern: %s \n"%(filepath_pattern)
	text += "Tried %d times with actual file paths: \n"%(_FileExists_max_retry)
	for i in range(_FileExists_max_retry):
		text += "  %s\n"%(filepaths[i])
	
	raise Err_irsync(text)


class Generator:
	# a clever helper class: https://stackoverflow.com/a/34073559/151453
	# to make generator object explicit to caller code, so that caller code
	# can later fetch the generator's return value.
    def __init__(self, gen):
        self.gen = gen

    def __iter__(self):
	    # self.retvalue is the generator function's "true" return value
        self.retvalue = yield from self.gen

def y_run_exe_with_time_limit(cmd_args, max_run_secs=0, dict_Popen_args={}):

	with subprocess.Popen(cmd_args,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT, # these two are important
	 		**dict_Popen_args) as subproc:

		with pipe_process_with_timeout(subproc, 0, max_run_secs) as watchdog:
			for linebytes in subproc.stdout:
				if not linebytes:
					break # sub-process has ended
				yield linebytes #print("###%s" % (linebytes.decode('utf8')), end='')
				watchdog.feed_dog()

	return (subproc.returncode, watchdog.uesec_timeout_fired) # return a tuple: subprocess exitcode and force-kill uesec

def run_exe_log_output_and_print(cmd_args, max_run_secs, dict_Popen_args={}, logfile_handle=None):
	
	gen_childoutput = Generator(y_run_exe_with_time_limit(cmd_args, max_run_secs, dict_Popen_args))
	for line in gen_childoutput:
		textline = line.decode("utf8")
		if logfile_handle:
			logfile_handle.write(textline)
		print(textline, end='')

	(child_exitcode, kill_at_uesec) = gen_childoutput.retvalue
	return (child_exitcode, kill_at_uesec)


def run_exe_grab_output_with_timeout(cmd_args, max_run_secs, dict_Popen_args={}):
	gen_childoutput = Generator(y_run_exe_with_time_limit(cmd_args, max_run_secs, dict_Popen_args))
	output = ""
	for line in gen_childoutput:
		textline = line.decode("utf8")
		output += textline

	(child_exitcode, kill_at_uesec) = gen_childoutput.retvalue
	return (child_exitcode, output, kill_at_uesec)


if __name__=='__main__':
	pass
