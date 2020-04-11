#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os
import re
import datetime
from enum import Enum # since Python 3.4

from .share import *

class irsync_st:
	
	class msglevel(Enum):
		dbg = "[DBG]"
		info = "[INFO]"
		warn = "[WARN]"
		err = "[ERROR]"
	
	datetime_pattern_default = "YYYYMMDD.hhmmss"
	
	def __init__(self, rsync_url, local_store_dir, local_shelf="", datetime_pattern=""):
		self.rsync_url = rsync_url
		self.local_store_dir = local_store_dir
		self.datetime_pattern = datetime_pattern if datetime_pattern else __class__.datetime_pattern_default
	
		if not local_shelf:
			pass # later: will set to final word of rsync url
	
		#
		# prepare some static working data
		#
		
		# combine server-name and shelf-name into `ushelf` name (货架标识符).
		# 'u' implies unique, I name it so bcz I expect/hope it is unique within 
		# a specific local_store_dir .
		server, spath = _check_rsync_url(rsync_url)
		if not local_shelf:
			local_shelf = spath.split("/")[-1] # final word of spath
		
		self.ushelf_name = "%s.%s"%(server, local_shelf)
		
		# datetime_sess: this backup session's datetime string
		# Sample: 
		#		20200411.213300
		#		2020-04-11
		#
		self.datetime_sess = datetime_by_pattern(self.datetime_pattern)
		
		self.finish_dirpath = os.path.join(self.local_store_dir, self.datetime_sess, self.ushelf_name)
			# Final backup content will be placed in this dirpath. 
			# The dirpath consists of three parts:
			# local_store_dir / datetime_sess / ushelf_name

		# Backup content transferring is first conveyed into a .working folder, and upon transfer finish,
		# it will then be moved into its finish_dirpath, for the purpose of being atomic.
		# Memo: I place .working folder directly at local_store_dir(instead of in datetime_sess subfolder)
		# bcz of eye-catching purpose.
		#
		self.working_dirname = "[{1}].{0}.working".format(self.datetime_sess, self.ushelf_name)
		self.working_dirpath = os.path.join(self.local_store_dir, self.working_dirname)
		
		# Previous-backup info enable us to do incremental backup.
		#
		self.prev_backup_inifile = os.path.join(self.local_store_dir, "[{}].prev".format(self.ushelf_name))
		
		# logging filename and its handle. If error, raise exception.
		#
		self.logfile , self.logfh = self.create_logfile()
		
		self._print_yield = False

	@property
	def is_print_yield(self):
		return self._print_yield
	
	@is_print_yield.setter
	def is_print_yield(self, value):
		if type(value) != type(True):
			raise Err_irsync("Only True or False is allowed for .print_yield property!")
		self._print_yield = value

	def yield_message(self, msg): # Experimental. Not success yet!
		yield msg

	def create_logfile(self):
		filename_pattern = "%s.run*.log"%(self.datetime_sess)
		filepath_pattern = os.path.join(self.working_dirpath, filename_pattern)
		fp, fh = create_logfile_with_seq(filepath_pattern) # in share.py
		return fp, fh

	def prn(self, msglevel, msg):
		now = datetime.datetime.now()
		timestr = "[%04d%02d%02d.%02d%02d%02d.%03d]"%(now.year, now.month, now.day, 
			now.hour, now.minute, now.second, now.microsecond/1000)
		msgline = "%s%s %s\n"%(timestr, msglevel.value, msg)
		
		self.logfh.write(msgline)
		print(msgline)

	def dbg(self, msg):
		self.prn(__class__.msglevel.dbg, msg)

	def info(self, msg):
		self.prn(__class__.msglevel.info, msg)

	def warn(self, msg):
		self.prn(__class__.msglevel.warn, msg)

	def err(self, msg):
		self.prn(__class__.msglevel.err, msg)

	def run(self):
		self.info("irsync - run() start")
		
		self.info("irsync - run() end")
		


def _check_rsync_url(url):
	# url should be rsync://<server>/<srcmodule>
	m = re.match("rsync://([^/]+)/(.+)", url)
	if not m:
		raise Err_irsync("Wrong rsync url format: %s"%(url))
	
	# return (server-name, server-path)
	return m.group(1), m.group(2)

def irsync_fetch_once(rsync_url, local_store_dir, local_shelf="", datetime_pattern=""):
	
	_check_rsync_url(rsync_url)
	
	irs = irsync_st(rsync_url, local_store_dir, local_shelf, datetime_pattern)

	irs.is_print_yield = True
	irs.run()
	
	return True
	
