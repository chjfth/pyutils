#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os
import re

from .share import *

class irsync_st:
	
	datetime_pattern_default = "HHHHMMDD.hhmmss"
	
	def __init__(self, rsync_url, local_store_dir, local_shelf="", datetime_pattern=""):
		self.rsync_url = rsync_url
		self.local_store_dir = local_store_dir
		self.datetime_pattern = datetime_pattern if datetime_pattern else irsync_st.datetime_pattern_default
	
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
		
		self.datetime_now = datetime_by_pattern(self.datetime_pattern)
		
		self.finish_dirpath = os.path.join(self.local_store_dir, self.datetime_now, self.ushelf_name)
			# Final backup content will be placed in this dirpath. 
			# The dirpath consists of three parts:
			# local_store_dir / datetime_now / ushelf_name

		# Backup content transferring is first conveyed into a .working folder, and upon transfer finish,
		# it will then be moved into its finish_dirpath, for the purpose of being atomic.
		# Memo: I place .working folder directly at local_store_dir(instead of in datetime_now subfolder)
		# bcz of eye-catching purpose.
		#
		self.working_dirname = "[{1}].{0}.working".format(self.datetime_now, self.ushelf_name)
		self.working_dirpath = os.path.join(self.local_store_dir, self.working_dirname)
		
		# Previous-backup info enable us to do incremental backup.
		#
		self.prev_backup_inifile = os.path.join(self.local_store_dir, "[{}].prev".format(self.ushelf_name))
		
		self._print_yield = False

	@property
	def print_yield(self):
		return self._print_yield
	
	@print_yield.setter
	def print_yield(self, value):
		if type(value) != type(True):
			raise Err_irsync("Only True or False is allowed for .print_yield property!")
		self._print_yield = value

	def prn(self, msg):
		print("00000")
		if self._print_yield:
			print("cccc")
			yield msg
		else:
			print("dddd")
			print(msg)

	def run(self):
		print("rrrrr")
		self.prn("irsync - run() start")
		print("sssss")
		
		self.prn("irsync - run() end")
		


def _check_rsync_url(url):
	# url should be rsync://<server>/<srcmodule>
	m = re.match("rsync://([^/]+)/(.+)", url)
	if not m:
		raise Err_irsync("Wrong rsync url format.")
	
	# return (server-name, server-path)
	return m.group(1), m.group(2)

def irsync_fetch_once(rsync_url, local_store_dir, local_shelf="", datetime_pattern=""):
	
	_check_rsync_url(rsync_url)
	
	irs = irsync_st(rsync_url, local_store_dir, local_shelf, datetime_pattern)
	irs.run()
	
	
