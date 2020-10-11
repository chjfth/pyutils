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

	def __del__(self):
		self.unlock() # to-test

	@property
	def abslockpath(self):
		return os.path.abspath(self.lockpath)

	def lock(self):
		if is_windows:
			self._lock_windows()
		else:
			self._lock_unix()

	def unlock(self):
		if is_windows:
			self._unlock_windows()
		else:
			self._unlock_unix()

	def _record_pid_in_lockfile(self):
		self.fhlock.seek(0, 0)
		self.fhlock.truncate()
		self.fhlock.write("pid=%d" % (os.getpid()))  # to fix
		self.fhlock.flush()

	def _clear_pid_in_lockfile(self):
		# clear file content
		self.fhlock.seek(0, 0)
		self.fhlock.truncate()

	def _lock_unix(self):
		file_exist = os.path.isfile(self.lockpath)
		try:
			self.fhlock = open(self.lockpath, "r+" if file_exist else "w+")
		except OSError:
			raise Err_asfilelock(
				'Cannot %s "%s" as lockfile.'%("open" if file_exist else "create", self.abslockpath)
			)

		try:
			fcntl.flock(self.fhlock, fcntl.LOCK_EX|fcntl.LOCK_NB)

			# Lock success, record our pid into file content.
			self._record_pid_in_lockfile()

		except BlockingIOError:
			his_pid = AsFilelock.getpid_from_lckfile(self.fhlock)
			raise Err_asfilelock(
				'Cannot apply lock on file "%s"; it is probably locked by another process with pid=%d'%(
					self.abslockpath, his_pid
				)
			)
		return

	def _unlock_unix(self):
		if not self.fhlock:
			return

		self._clear_pid_in_lockfile()

		fcntl.flock(self.fhlock, fcntl.LOCK_UN)
		self.fhlock.close()
		self.fhlock = None

	def _lock_windows(self):
		try:
			os.remove(self.lockpath)
		except OSError:
			# Maybe PermissionError if the file is already opened by others,
			#    or FileNotFoundError if file does not exist yet.
			# Yes, just ignore this file deleting error.
			# The ensuing open(,'x+') will report the actual error.
			pass

		if os.path.isdir(self.lockpath):
			raise Err_asfilelock(
				'Cannot apply filelock on "%s" because it is a directory.'%(self.lockpath)
			)

		if os.path.exists(self.lockpath):
			raise Err_asfilelock(
				'To apply filelock on "%s", I have to remove the file first. '%(self.lockpath) +
				'But I failed to remove it. It may have been locked by others.'
			)

		try:
			self.fhlock = open(self.lockpath, 'x+')

			# Lock success, record our pid into file content.
			self._record_pid_in_lockfile()

		except OSError:
			raise Err_asfilelock(
				'Fail to place filelock on "%s" because it has been locked by others.'%(self.lockpath)
			)
		return

	def _unlock_windows(self):
		if not self.fhlock:
			return

		self._clear_pid_in_lockfile()

		# Close file handle(so that others can open it), means unlock.
		self.fhlock.close()
		self.fhlock = None
