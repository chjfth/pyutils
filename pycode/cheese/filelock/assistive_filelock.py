#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os
import re
import datetime
from enum import Enum,IntEnum # since Python 3.4
from collections import namedtuple

is_windows = os.name == 'nt'

if not is_windows:
    import fcntl

class Err_asfilelock(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg


class AsFilelock:

	@staticmethod
	def getpid_from_lckfile(fhlock):
		fhlock.seek(0, 0)
		text = fhlock.read()
		r = re.match(r"pid=([0-9]+)", text)
		if r:
			return int(r.group(1))
		else:
			return 0

	def __init__(self, filepath_as_lock):
		self.lockpath = filepath_as_lock
		self.fhlock = None

	def lock(self):
		if is_windows:
			assert(0) # lock_windows(self)
		else:
			self.lock_unix()

	def unlock(self):
		if is_windows:
			assert (0)  # lock_windows(self)
		else:
			self.unlock_unix()

	def lock_unix(self):
		file_exist = os.path.isfile(self.lockpath)
		try:
			self.fhlock = open(self.lockpath, "r+" if file_exist else "w+")
		except OSError:
			raise Err_asfilelock(
				'Cannot %s "%s" as lockfile.'%("open" if file_exist else "create", self.lockpath)
			)

		try:
			fcntl.flock(self.fhlock, fcntl.LOCK_EX|fcntl.LOCK_NB)

			# If lock success, record our pid into file content.
			self.fhlock.seek(0, 0)
			self.fhlock.truncate()
			self.fhlock.write("pid=%d"%(os.getpid)) # to fix
			self.fhlock.flush()

		except BlockingIOError:
			his_pid = AsLockfile.getpid_from_lckfile(self.fhlock)
			raise Err_asfilelock(
				'Cannot apply lock on file "%s"; it is probably locked by another process with pid=%d'%(
					self.lockpath, his_pid
				)
			)
		pass

	def unlock_unix(self):
		if not self.fhlock:
			return
		fcntl.flock(self.fhlock, fcntl.LOCK_UN)


