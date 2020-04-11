
# print("[%s] __name__=%s"%(__file__,__name__))

import datetime

class Err_irsync(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg


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