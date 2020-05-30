#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os
import re
import datetime
from enum import Enum,IntEnum # since Python 3.4
from collections import namedtuple

from .share import *

LOG_NOD = 'logs' # as directory node name for storing log files.

class MsgLevel(IntEnum):
	err = 1
	warn = 2
	info = 3
	dbg = 4

class irsync_st:

	pfxMsgLevel = [""]*5
	pfxMsgLevel[MsgLevel.err.value] = "[ERROR]"
	pfxMsgLevel[MsgLevel.warn.value] = "[WARN]"
	pfxMsgLevel[MsgLevel.info.value] = "[INFO]"
	pfxMsgLevel[MsgLevel.dbg.value] = "[DBG]"
	
	datetime_pattern_default = "YYYYMMDD.hhmmss"
	
	def _save_extra_args(self, args, argname, selfattr_desiredtype, selfattr_name):
		if argname in args:
			argval = args[argname]
			if type(argval) != selfattr_desiredtype: # check argument type validity
				raise Err_irsync("You passed a wrong type to irsync initializing parameter '%s'. Desired type is '%s'."%(
					argname, 
					"%s.%s"%(selfattr_desiredtype.__module__, selfattr_desiredtype.__name__) # sample: cheese.incremental_rsync.client.MsgLevel
					)) 
			setattr(self, selfattr_name, argval)
	
	def __init__(self, rsync_url, local_store_dir, local_shelf="", datetime_pattern="", **args):

		# [local_store_dir]/[server.local_shelf] becomes final target dir for rsync.
		
		#
		# Some parameter validity checking.
		#

		if datetime_pattern.find(' ')>=0:
			raise Err_irsync("Error: You assign datetime_pattern='%s', which contains space."%(datetime_pattern))

		#
		# Set default working parameters.
		#
		
		self.rsync_url = rsync_url
		self.local_store_dir = os.path.abspath(local_store_dir)
		self.datetime_pattern = datetime_pattern if datetime_pattern else __class__.datetime_pattern_default
	
		if not local_shelf:
			pass # later: will set to final word(token) of rsync url

		self._loglevel = MsgLevel.info
		
		#
		# Process extra optional arguments
		#
		self._save_extra_args(args, 'loglevel', MsgLevel, '_loglevel')
	
		#
		# prepare some static working data
		#
		
		# combine server-name and shelf-name into `ushelf` name (货架标识符).
		# 'u' implies unique, I name it so bcz I expect/hope it is unique within 
		# a specific local_store_dir .
		server, spath = _check_rsync_url(rsync_url)
		server_goodchars = server.replace(':', '~') # ":" is not valid Windows filename, so change it to ~

		if not local_shelf:
			local_shelf = spath.split("/")[-1] # final word of spath
		
		self.ushelf_name = "%s.%s"%(server_goodchars, local_shelf)
		
		# datetime_vault: this backup session's datetime-identified vault
		# Examples: 
		#		20200411.213300
		#		2020-04-11
		#
		self.datetime_vault = datetime_by_pattern(self.datetime_pattern)
		
		self.finish_dirpath = os.path.join(self.local_store_dir, self.datetime_vault, self.ushelf_name)
			# Final backup content will be placed in this dirpath. 
			# The dirpath consists of three parts:
			# local_store_dir / datetime_vault / ushelf_name

		# Backup content transferring is first conveyed into a .working folder, and upon transfer finish,
		# it will then be moved into its finish_dirpath, for the purpose of being atomic.
		# Memo: I place .working folder directly at local_store_dir(instead of in datetime_vault subfolder)
		# bcz of eye-catching purpose.
		#
		self.working_dirname = "{0}@[{1}].working".format(self.datetime_vault, self.ushelf_name)
		self.working_dirpath = os.path.join(self.local_store_dir, self.working_dirname)
		
		# Previous-backup info enable us to do incremental backup.
		#
		self.prev_ushelf_inifile = os.path.join(self.local_store_dir, "[{}].prev".format(self.ushelf_name))
		
		# logging filename and its handle. If error, raise exception.
		#
		self.logfile , self.logfh = self.create_logfile()
		

	@property
	def loglevel(self):
		return self._loglevel
	
	@loglevel.setter
	def loglevel(self, level):
		self._loglevel = level

	def create_logfile(self):
		filename_pattern = "%s.run*.log"%(self.datetime_vault)
		filepath_pattern = os.path.join(self.working_dirpath, LOG_NOD, filename_pattern)
		fp, fh = create_logfile_with_seq(filepath_pattern) # in share.py
		return fp, fh

	def prn(self, msglevel, msg):

		if self.loglevel.value < msglevel.value:
			return

		lvn = msglevel.value
		lvs = __class__.pfxMsgLevel[lvn]
		
		msgline = "[%s]%s %s\n"%(datetime_now_str(), lvs , msg)
		
		self.logfh.write(msgline)
		print(msgline, end="")

	def err(self, msg):
		self.prn(MsgLevel.err, msg)
		raise Err_irsync(msg) # On err, we raise Exception to conclude our work.

	def warn(self, msg):
		self.prn(MsgLevel.warn, msg)

	def info(self, msg):
		self.prn(MsgLevel.info, msg)

	def dbg(self, msg):
		self.prn(MsgLevel.dbg, msg)

	def prn_start_info(self):
		pass

	def run(self):
		"""
		Return normally on success, raise Exception on error.
		"""
		
		self.info("irsync - run() start")
		
		# Check whether finish-dirpath has existed, if so, the backup has done already.
		
		if os.path.exists(self.finish_dirpath):
			if os.path.isdir(self.finish_dirpath):
				self.info("Backup already done in directory: %s"%(self.finish_dirpath))
				return
			else:
				self.err("I need to create backup directory '%s', but it appears to be a file in the way."%(
					self.finish_dirpath))
		
		os.makedirs(self.working_dirpath, exist_ok=True)
		
		line_sep78 = '='*78
		
		#
		# Run rsync exe and capture its output to log file.
		#
		rsync_cmd = "rsync -v -a %s %s"%(self.rsync_url, self.working_dirpath)
		#
		# If irsync primary logfile(self.logfile) is 20200414.run0.log, 
		# We will create rsync logfile with pattern 20200414.run0.rsync*.log ,
		# so that we know the "...rsync0.log", "...rsync1.log" belongs to run0.
		rsync_logfile_pattern = '.rsync*'.join(os.path.splitext(self.logfile))
		fp_rsync, fh_rsync = create_logfile_with_seq(os.path.join(self.working_dirpath, rsync_logfile_pattern))
		#
		self.info(""":
  Now running:   %s
  With log file: %s (in same directory as this one)
%s
"""%(rsync_cmd, os.path.basename(fp_rsync), line_sep78))
		#
		# Add some banner text at start of fp_rsync.
		fh_rsync.write("""[%s] This is the console output log of shell command:
    %s
%s
"""%(datetime_now_str(), rsync_cmd, line_sep78))
		#
		exitcode = run_exe_log_output_and_print(rsync_cmd, {"shell":True}, fh_rsync)
		
		if exitcode==0:
			self.info("Rsync run success.")
		else:
			self.warn("Rsync run fail, exitcode=%d"%(exitcode))
			raise Err_rsync_exec(exitcode, self.ushelf_name)
		
		self.info("irsync - run() end")

		# Move .working-directory into finish-directory
		#
		fh_rsync.close()
		self.logfh.close()
		os.makedirs(os.path.dirname(self.finish_dirpath), exist_ok=True) # create its parent dir
		os.rename(self.working_dirpath, self.finish_dirpath)
		
#		self.info("A backup action has just finished at: %s"%(self.finish_dirpath))
		
		


def _check_rsync_url(url):
	# url should be rsync://<server>/<srcmodule>
	m = re.match("rsync://([^/]+)/(.+)", url)
	if not m:
		raise Err_irsync("Wrong rsync url format: %s"%(url))
	
	# return (server-name, server-path)
	return m.group(1), m.group(2)



def irsync_fetch_once(rsync_url, local_store_dir, local_shelf="", datetime_pattern="", **args):
	
	_check_rsync_url(rsync_url)
	
	irs = irsync_st(rsync_url, local_store_dir, local_shelf, datetime_pattern, **args)

	irs.run()
	
	return True
	
