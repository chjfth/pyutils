
# print("[%s] __name__=%s"%(__file__,__name__))

import os
import re
import datetime
import glob

class Err_irsync(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg

class err_FileExists(Exception): # internal use
	def __init__(self, errfilepath):
		self.errfilepath = errfilepath


def datetime_by_pattern(pattern):
	# Example: pattern="YYYYMMDD.hhmmss"
	# Return: "20200411.153300"
	
	now = datetime.datetime.now()
	
	dt = pattern
	dt = dt.replace("YYYY", "%04d"%(now.year))
	dt = dt.replace("MM", "%02d"%(now.month))
	dt = dt.replace("DD", "%02d"%(now.day))
	dt = dt.replace("hh", "%02d"%(now.hour))
	dt = dt.replace("mm", "%02d"%(now.minute))
	dt = dt.replace("ss", "%02d"%(now.second))
	return dt

def _create_logfile_with_seq_once(filepath_pattern):
	
	# Example: filepath_pattern = "/rootdir/run*.log"
	# Result: "/rootdir/run1.log" or "/rootdir/run2.log" ... will be created.
	# If FileExistsError is raised, the caller should try calling it again.
	
	dirpath, filename_pattern = os.path.split(filepath_pattern)
	
	if filename_pattern.count('*') != 1:
		raise Err_irsync("BUG: filepath_pattern does not contain an single '*': %s"%(filepath_pattern))
	
	existings = glob.glob(filepath_pattern)
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
	filepath_pattern should have a single '*' in it.
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
		text += "  %s\n"%(filepath[i])
	
	raise Err_irsync(text)
