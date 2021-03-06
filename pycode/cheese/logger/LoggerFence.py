#!/usr/bin/env python3
# coding: utf-8

import os, sys, time
import traceback
from contextlib import contextmanager


class LoggerFence:

	def __init__(self, logcall):
		self.__logcall = logcall
		
		self.nested = 0 # not private, can improve?
		self.excpt_count = 0

	def set_logcall(self, logcall):
		self.__logcall = logcall

	def mark_api(func):
		# func is an unbound function
		def wrapper(self, *args, **kwargs):
			self.nested += 1
			try:
				ret = func(self, *args, **kwargs)
			except:
				# We log the exception for current-module and let the exception propagate.
				if self.nested == 1:
					self.excpt_count += 1
					excpt_text = traceback.format_exc()
					self.__logcall(excpt_text)
				raise
			finally:
				self.nested -= 1
			return ret

		return wrapper


@contextmanager
def LiveFence(logcall):
	try:
		yield
	except:
		# We log the exception for current-module and let the exception propagate.
		excpt_text = traceback.format_exc()
		logcall(excpt_text)
		raise

def test1():
	fh = open("mylog.txt", "a", encoding="utf8")
	fh.write( time.strftime('%Y-%m-%d %H:%M:%S\n', time.localtime()) )

	with LiveFence(fh.write) as sth:
	    result = DoDiv(6, 2)
	    fh.write("DoDiv returns: %d\n"%(result))

	with LiveFence(fh.write) as sth:
	    result = DoDiv(6, 0) # this will cause exception
	    fh.write("DoDiv returns: %d\n"%(result))

