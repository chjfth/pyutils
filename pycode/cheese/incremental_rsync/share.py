#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, subprocess
import re
import datetime
import glob
from enum import Enum,IntEnum # since Python 3.4

class MsgLevel(IntEnum):
	err = 1
	warn = 2
	info = 3
	dbg = 4

class Err_irsync(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg

class Err_rsync_exec(Err_irsync):
	def __init__(self, exitcode, ushelf):
		errmsg = "rsync execution error, exitcode=%d. (ushelf=%s)"%(exitcode, ushelf)
		super().__init__(errmsg)
	

class err_FileExists(Exception): # internal use
	def __init__(self, errfilepath):
		self.errfilepath = errfilepath


def datetime_now_str():
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


# Thanks to: https://stackoverflow.com/a/34115590/151453
# A portable solution is to use a thread to kill the child process if reading a line takes too long.

from threading import Event, Lock, Thread
from subprocess import Popen, PIPE, STDOUT
from time import monotonic  # use time.time or monotonic.monotonic on Python 2

class WatchdogTimer(Thread):
    """Run *callback* in *timeout* seconds unless the timer is restarted."""

    def __init__(self, timeout, callback, *args, timer=monotonic, **kwargs):
        super().__init__(**kwargs)
        self.timeout = timeout
        self.callback = callback
        self.args = args
        self.timer = timer
        self.cancelled = Event()
        self.blocked = Lock()

    def run(self):
        self.restart() # don't start timer until `.start()` is called
        # wait until timeout happens or the timer is canceled
        while not self.cancelled.wait(self.deadline - self.timer()):
            # don't test the timeout while something else holds the lock
            # allow the timer to be restarted while blocked
            with self.blocked:
                if self.deadline <= self.timer() and not self.cancelled.is_set():
                    # print("calling back..........") # debug
                    return self.callback(*self.args)  # on timeout

    def restart(self):
        """Restart the watchdog timer."""
        self.deadline = self.timer() + self.timeout

    def cancel(self):
        self.cancelled.set()


# Thanks to: https://stackoverflow.com/a/34115590/151453
# A portable solution is to use a thread to kill the child process if reading a line takes too long.
#
from threading import Event, Lock, Thread
from time import monotonic  # use time.time or monotonic.monotonic on Python 2
#
class WatchdogTimer(Thread):
	"""Run *callback* in *timeout* seconds unless the timer is restarted."""

	def __init__(self, timeout, callback, *args, timer=monotonic, **kwargs):
		super().__init__(**kwargs)
		self.timeout = timeout
		self.callback = callback
		self.args = args
		self.timer = timer
		self.cancelled = Event()
		self.blocked = Lock()

	def run(self):
		self.restart() # don't start timer until `.start()` is called
		# wait until timeout happens or the timer is canceled
		while not self.cancelled.wait(self.deadline - self.timer()):
			# don't test the timeout while something else holds the lock
			# allow the timer to be restarted while blocked
			with self.blocked:
				if self.deadline <= self.timer() and not self.cancelled.is_set():
					print("Killing back subprocess......") # debug
					return self.callback(*self.args)  # on timeout

	def restart(self):
		"""Restart the watchdog timer."""
		self.deadline = self.timer() + self.timeout

	def cancel(self):
		self.cancelled.set()


class Generator:
	# a clever helper class: https://stackoverflow.com/a/34073559/151453
	# to make generator object explicit to caller code, so that caller code
	# can later fetch the generator's return value.
    def __init__(self, gen):
        self.gen = gen

    def __iter__(self):
        self.retvalue = yield from self.gen

def y_run_exe_log_output(cmd_args, timeout_sec, dict_Popen_args):

	with subprocess.Popen(cmd_args,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT, # these two are important
	 		**dict_Popen_args) as subproc:

		if timeout_sec==0:
			while True:
				line = subproc.stdout.readline()
				if not line:  # this means child-process has ended.
					break
				yield line

		else: # need readline() timeout
			# Thanks to: https://stackoverflow.com/a/34115590/151453

			# kill subproc in timeout seconds unless the timer is restarted
			watchdog = WatchdogTimer(timeout_sec, callback=subproc.kill, daemon=True)
			watchdog.start()
			for line in subproc.stdout:
				yield line
				# Note: won't invoke the watchdog callback if do_something() takes too long
				with watchdog.blocked:
					if False:  # not do_something(line):  # some criterion is not satisfied
						subproc.kill()
						break
					watchdog.restart()  # restart timer just before reading the next line
			watchdog.cancel()

	subproc.wait() # we know that child-process should have exited.
	return subproc.returncode # return child-process exit-code

def run_exe_log_output_and_print(cmd_args, timeout_sec, dict_Popen_args, logfile_handle):
	
	gen_childoutput = Generator(y_run_exe_log_output(cmd_args, timeout_sec, dict_Popen_args))
	for line in gen_childoutput:
		textline = line.decode("utf8")
		logfile_handle.write(textline)
		print(textline, end='')

	return gen_childoutput.retvalue # return child-process exit-code
