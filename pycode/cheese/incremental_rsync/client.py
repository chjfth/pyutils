#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, sys, re
import datetime
from enum import Enum,IntEnum # since Python 3.4
from collections import namedtuple

from cheese.filelock.assistive_filelock import AsFilelock, Err_asfilelock

from .share import *
from .helper import *

LOG_NOD = 'logs' # as directory node name for storing log files.

IRSYNC_INI_FILENAM ='irsync.ini'
INISEC_last_success_dirpath = 'last_success_dirpath'

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

	@property
	def master_logfile(self):
		return os.path.join(self.local_store_dir, "irsync.log")

	@property
	def master_logfile_lck(self):
		return self.master_logfile + ".lck"

	@property
	def ini_filepath(self):
		return os.path.join(self.local_store_dir, IRSYNC_INI_FILENAM)

	def __init__(self, rsync_url, local_store_dir, local_shelf="", datetime_pattern="", **args):

		# [local_store_dir]/[datetime_vault]/[server.local_shelf] becomes final target dir for rsync.
		# [server.local_shelf] is called [ushelf] for brevity.

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
		# for easy eye-catching.
		#
		self.working_dirname = "{0}@[{1}].working".format(self.datetime_vault, self.ushelf_name)
		self.working_dirpath = os.path.join(self.local_store_dir, self.working_dirname)
		
		# Previous-backup info enable us to do incremental backup.
		#
		self.prev_ushelf_inifile = os.path.join(self.local_store_dir, "[{}].prev".format(self.ushelf_name))

		self.master_logfile_start()
		return

	def master_logfile_start(self):
		#
		# Acquire master-logfile's filelock first, so to ensure we're the only process
		# that is storing into this local_store_dir. If acquire-filelock fails, just quit.
		#
		self.master_filelock = AsFilelock(self.master_logfile_lck)

		try:
			self.master_filelock.lock()
		except Err_asfilelock as e:
			# We have no logfile to write here, so just print to stderr.
			sys.stderr.write("""
Error:  Cannot acquire lock on local_store_dir "%s", so I cannot continue.      
Detail: %s
"""%(self.local_store_dir, e.errmsg))
			exit(4)

		self.master_logfh = open(self.master_logfile, "a")
		self.master_logfh.write("\n~\n") # We don't want timestamp on this linesep char

		self.prn_masterlog("""Irsync session start.
    rsync_url:                {}
    local_store_dir(working): {}
    local_store_dir(finish) : {}
""".format  (
            self.rsync_url,
            self.working_dirpath,
            self.finish_dirpath
		    )
		)
		return

	def master_logfile_end(self):
		self.prn_masterlog('Irsync session success. Get your backup at "%s"'%(self.finish_dirpath))
		## todo: Tell extra info like time used etc.

		self.master_filelock.unlock()
		self.master_logfh.close()

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

	def prn_masterlog(self, msg):
		msgline = "[%s]%s\n" % (datetime_now_str(), msg)

		self.master_logfh.write(msgline)
		self.master_logfh.flush()

		print(msgline, end="")

	def prn_start_info(self):
		pass

	def run(self):
		"""
		Return normally on success, raise Exception on error.
		"""

		# Check whether finish-dirpath has existed, if so, the backup has done already.
		
		if os.path.exists(self.finish_dirpath):
			if os.path.isdir(self.finish_dirpath):
				self.prn_masterlog(
					"The local_store_dir(finish) has existed already. So I think the backup had been done some time ago.")
				return
			else:
				self.err("I need to create backup directory '%s', but it appears to be a file in the way."%(
					self.finish_dirpath))

		# Create session logging filename and save its handle. If error, raise exception.
		#
		try:
			self.sess_logfile, self.logfh = self.create_logfile()
			sesslog_d, sesslog_n = os.path.split(self.sess_logfile)
			assert( sesslog_d.startswith(self.working_dirpath) ) # sesslog_d has an extra 'logs' subdir
			self.prn_masterlog("""Session logfile can be found at:
    (working) : {}
    (finish)  : {}
""".format      (
				self.sess_logfile,
				self.sess_logfile.replace(self.working_dirpath, self.finish_dirpath)
				)
			)
		except:
			# todo:: in the future, may employ a more detailed error message stack.
			self.prn_masterlog("Unexpected! Fail to create a session logfile.")
			raise

		self.info("irsync session - run() start")

		os.makedirs(self.working_dirpath, exist_ok=True)
		
		line_sep78 = '='*78
		
		#
		# Run rsync exe and capture its output to log file.
		#
		rsync_cmd = "rsync --progress -v -a %s %s"%(self.rsync_url, self.working_dirpath)
		#
		# If irsync session logfile(self.sess_logfile) is 20200414.run0.log,
		# We will create rsync logfile with pattern 20200414.run0.rsync*.log ,
		# so that we know the "...rsync0.log", "...rsync1.log" belongs to run0.
		rsync_logfile_pattern = '.rsync*'.join(os.path.splitext(self.sess_logfile))
		fp_rsync, fh_rsync = create_logfile_with_seq(os.path.join(self.working_dirpath, rsync_logfile_pattern))
		#
		self.info(""":
  Now running  : %s
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
		
		self.info("irsync session - run() end")

		# Move .working-directory into finish-directory
		#
		fh_rsync.close()
		self.logfh.close()
		self.logfh = None

		try:
			os.makedirs(os.path.dirname(self.finish_dirpath), exist_ok=True) # create its parent dir
			os.rename(self.working_dirpath, self.finish_dirpath) # move and rename the dir
		except OSError:
			raise Err_irsync("Error: Irsync session succeeded, but fail to move working directory to finish directory.")

		# Record [last_success_dirpath] into rsync.ini
		try:
			WriteIniItem(self.ini_filepath, INISEC_last_success_dirpath,
		             self.ushelf_name, self.finish_dirpath)
		except OSError:
			raise Err_irsync('Error: Cannot record [%s] information into file "%s"'%(
				INISEC_last_success_dirpath, self.ini_filepath))


		self.master_logfile_end()

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
	
