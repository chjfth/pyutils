#!/usr/bin/env python3
# coding: utf-8

from selfclear_tempfile.selfclear_tempfile import IFilesys

class FakeFs(IFilesys):
	"""A fake filesytem which is merely enough for selfclear_tempfile auto-testing.
	
	I use a dict to represent a filesytem directory. 
	The key is the filepath, and the value is the timestamp.
	"""
	
	def __init__(self):
		self._dir = {}
	

	def listdir(self, dirpath):
		return self._dir.keys()

	def mkdir(self, dirpath):
		pass

	def t_createfile(self, filepath, uesec_ctime=None):
		if filepath in self._dir:
			raise FileExistsError(filepath)
		else:
			assert uesec_ctime>=0
			self._dir[filepath].uesec_ctime


	def createopenfile(self, filepath, mode, **kwargs):
		assert False


	def removefile(self, filepath):
		try:
			del self._dir[filepath]
		except KeyError:
			raise FileNotFoundError(filepath)
	

	def get_ctime(self, filepath):
		try:
			return self._dir[filepath]
		except KeyError:
			raise FileNotFoundError(filepath)
	

	def get_mtime(self, filepath):
		return self.get_ctime(filepath)
	

	def update_mtime(self, filepath, uesec):
		try:
			self._dir[filepath] = uesec
		except KeyError:
			raise FileNotFoundError(filepath)
		
