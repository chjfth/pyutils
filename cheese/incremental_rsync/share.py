
print("000")

class Err_irsync(Exception):
	def __init__(self, errmsg, errcode):
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg

