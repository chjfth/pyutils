#!/usr/bin/env python3
# coding: utf-8

from abc import ABC, abstractmethod
import os, sys, time

class IFilesys(ABC):
	"""Use this abstract class to simulate a file system.
	
	When unit-testing selfclear_tempfile, we will use a simulated filesystem.
	
	'I' implies Interface.
	"""

	@abstractmethod
	def listdir(self, dirpath):
		"""Same as os.listdir()"""

	@abstractmethod
	def mkdir(self, dirpath):
		"""Same as os.mkdir(). FileExistsError if existed."""

	@abstractmethod
	def t_createfile(self, filepath, uesec_ctime=None):
		"""Create a file with given filepath, and set its creation time to uesec_ctime.

		If uesec_ctime==None, use current system time.
		
		uesec is the seconds count since Unix Epoch.
		
		This functions is only for unittest.
		
		Return the filepath created.
		If error occurs, throw exeception:
		* Specified filename already existed.
		* Meet a read-only dirpath.
		"""

	@abstractmethod
	def createopenfile(self, filepath, mode, **open_kwargs):
		"""Create a new file with specified name and open it for writing.
		
		filepath, mode, and **open_kwargs will be passed to sys built-in open().
		
		User should ensure he gives appropriate mode value.
		
		This function is not used in unittest.
		
		Return behavior is totally determined by open().
		
		"""

	@abstractmethod
	def removefile(self, filepath):
		"""Remove specified file.
		
		Return value tells whether the removal succeeds.
		If it fails, it probably means that file is still in use, not considered an error.
		"""

	@abstractmethod
	def get_ctime(self, filepath):
		"""Get creation time of filepath, should return an int. 
		E: OSError
		"""
	
	@abstractmethod
	def get_mtime(self, filepath):
		"""Get modification time of filepath. should return an int. 
		E: OSError
		Will only do this for .clearcheck file.
		"""
	
	@abstractmethod
	def update_mtime(self, filepath, uesec):
		"""Update modification time of filepath.
		Will only do this for .clearcheck file.
		"""


class RealFs(IFilesys):
	"""A real filesytem which support underlying operations.
	"""
	def __init__(self):
		pass

	def listdir(self, dirpath):
		return os.listdir(dirpath)

	def mkdir(self, dirpath):
		os.mkdir(dirpath)

	def t_createfile(self, filepath, uesec_ctime=None):
		assert False

	def createopenfile(self, filepath, mode, **kwargs):
		fh = open(filepath, mode, **kwargs)
		return fh

	def removefile(self, filepath):
		os.remove(filepath)

	def get_ctime(self, filepath):
		ret = int( os.path.getctime(filepath) )
		return ret

	def get_mtime(self, filepath):
		ret = int( os.path.getmtime(filepath) )
		return ret
	
	def update_mtime(self, filepath, uesec=None):
		if uesec:
			os.utime(filepath, (uesec, uesec))
		else:
			os.utime(filepath, None)


realfs = RealFs()


class SelfclearTempfile: # todo: add set current time for unittest
	
	def __init__(self, dirpath, 
			prefix='temp', 
			suffix='.tmp',
			preserve_seconds=3600, 
			scan_delay_seconds=60,
			filesys=realfs):
		
		self._dirpath = dirpath
		self._prefix = prefix
		self._suffix = suffix
		self._preserve_seconds = preserve_seconds
		self._scan_delay_seconds = scan_delay_seconds
		self._filesys = filesys
		
		# vars for debugging/testing
		self._scandir_count = 0
#		self._uesec_emu = None # only for unittest, emulate current time

	@property
	def cleancheck_filepath(self):
		ret = os.path.join(self._dirpath, self._prefix+".cleancheck")
		return ret
	
	def listfiles(self):
		return self._filesys.listdir()
	
#	def is_prefix_match(self, filepath):
#		filename = os.path.basename(filepath)
#		if filename.startswith(self._prefix):
#			return True
#		else:
#			return False
	
	def create_new(self, uesec_nowf=None, openmode="t", **open_kwargs):
		"""Create a tempfile and open that file, returning its file handle.
		
		uesec_nowf: None means use current time(=real environment, not unittesting)
		
		openmode is passed to builtin open(). I will apply 'x' flag to ensure creating
		a new file. User should not include 'r,w,a' in openmode, otherwise raise ValueError.
		
		**open_kwargs are passed to built-in open().
		
		"""
		
		# Check for bad params first.
		if 'r' in openmode or 'w' in openmode or 'a' in openmode:
			raise ValueError("openmode parameter should not include any of 'r,w,a'")
		
		fs = self._filesys
		
		if uesec_nowf==None:
			is_realfs = True
			uesec_nowf = time.time()
		else:
			is_realfs = False
		
		# Create _dirpath if not exist.
		#
		try:
			self._filesys.mkdir(self._dirpath)
		except FileExistsError:
			pass
		except:
			raise
		
		is_clean_old = False
		
		# Determine whether scan_delay_seconds has been elapsed since last call,
		# if so, update temp.cleancheck's timestamp.
		#
		try:
			uesec_lastchk = fs.get_mtime(self.cleancheck_filepath)
			
			if uesec_nowf-uesec_lastchk >= self._scan_delay_seconds:
				is_clean_old = True
				fs.update_mtime(self.cleancheck_filepath)
				
		except OSError: # must be file-not-exist
			is_clean_old = True #uesec_lastchk = 0
			fs.createopenfile(self.cleancheck_filepath, "w").close()
		
		if is_clean_old:
			self._clean_old_tempfiles(uesec_nowf)
		
		filehandle = self._create_new_tempfile(is_realfs, uesec_nowf, openmode, **open_kwargs)
		
		return filehandle
	
	
	def _clean_old_tempfiles(self, uesec_now):
		
		fs = self._filesys
		
		def isclear(filepath):
			if not os.path.basename(filepath).startswith(self._prefix):
				return False
			
			ctime = fs.get_ctime(filepath)
			if uesec_now-ctime < self._preserve_seconds:
				return False
			
			return True
		
		files = fs.listdir(self._dirpath)
		self._scandir_count += 1
		
		clear_filepaths = [f for f in files if isclear(f)]
		
		for filepath in clear_filepaths:
			try:
				fs.removefile(filepath)
			except OSError:
				pass
	
	def _create_new_tempfile(self, is_realfs, uesec_nowf, openmode, **open_kwargs):
		""" Create new tempfile according to current uesec. 
		The created filename will represent localtime YYMMDD_hhmmss.mmm .
		For example, prefix is "everpic-", suffix is ".png", the result will be sth like:
		
			everpic-20180719_103128.766.png
		
		If you create many tempfiles within one single millisecond, there will be extra suffix, like:
		
			everpic-20180719_103128.766.t1.png
			everpic-20180719_103128.766.t2.png
			...
			everpic-20180719_103128.766.t99.png
		"""
		fs = self._filesys

		millsec_part = uesec_nowf*1000%1000
		tmlocal = time.localtime(uesec_nowf) 
		tmstr = time.strftime('%Y%m%d_%H%M%S', tmlocal) + ".%03d"%(millsec_part)
		
		if not 'x' in openmode:
			openmode = 'x'+openmode # force exclusive open, do not overwrite existing
			
		tpart = ""
		retry = 0
		while retry<100:
			filename = self._prefix + tmstr + tpart + self._suffix
			newfilepath = os.path.join(self._dirpath, filename)
			
			try:
				if is_realfs:
					fh = fs.createopenfile(newfilepath, openmode, **open_kwargs)
					return fh
				else:
					fs.t_createfile(newfilepath, uesec_nowf)
					return None
			except OSError:
				retry += 1
				tpart = ".t%d"%(retry)
		
		raise OSError("selfclear_tempfile cannot create a file for you after many retres.")


def create(targetdir, openmode="t", prefix='temp', suffix='.tmp',
			preserve_seconds=3600, 
			scan_delay_seconds=60,
			**open_kwargs):
	sctf = SelfclearTempfile(targetdir, prefix, suffix, preserve_seconds, scan_delay_seconds)
	
	ret = sctf.create_new(None, openmode, **open_kwargs)
	return ret


def myprint():
	print("woho")

