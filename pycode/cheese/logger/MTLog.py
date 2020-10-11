#!/usr/bin/env python3
# coding: utf-8

"""
MTLog means Multi-Target Logger.

When a piece of application code generates a piece of log message, that log message may be dispatched(=copied)
to multiple target. For example, the message may be printed to CMD console, or as well be written to a logfile.

So, MTLog is the class to help you do the dispatching.

Each dispatch target is associated with a "level", more exactly, a "sink-level". The "source-level"
is assigned by the caller with each input message. If sink_level>=source_level, the "sink" takes place,
i.e. the corresponding target "receives" the messsage(e.g., use sees console output, message written to file).

Mnemonics:
* source-level tells how verbose the message is, the larger value, the more verbose.
* sink-level tells how verbose the logger wants to record the messsage.

MTLog accepts each piece of message atomically, and will prepend timestamp and append line-ending for it.

"""

import time, math
from collections import namedtuple
from cheese.pycook3.classhelper import typed_property

class MTLog:

	Target = namedtuple('Target', "sinklevel logcall")

	datetime_format = typed_property('datetime_format', str, '__')
	need_millisec = typed_property('need_millisec', bool, '__')
	need_levelname = typed_property('need_levelstr', bool, '__')

	def __init__(self, datetime_format='%Y%m%d.%H%M%S', need_millisec=False, need_levelname=False):
		self.__targets = {}
		self.__level2name = {}
		self.datetime_format = datetime_format
		self.need_millisec = need_millisec
		self.need_levelname = need_levelname


	def add_target(self, targetname, sinklevel, logcall):
		self.__targets[targetname] = __class__.Target(sinklevel, logcall)
		self.__level2name[sinklevel] = targetname

	def datetime_str(self):
		uesec = time.time()
		tmlocal = time.localtime(uesec)
		timestr = time.strftime(self.datetime_format, tmlocal)

		if self.need_millisec:
			msec_part = int((uesec - math.floor(uesec)) * 1000 % 1000)
			timestr += ".%03d" % (msec_part)

		return timestr

	def log(self, sourcelevel, msg, targets='all'):
		"""Log a message to designated targets."""

		tgnames = targets
		if tgnames == 'all':
			tgnames = self.__targets.keys()
		elif type(tgnames)==str:
			tgnames = [tgnames] # a single ele array
		elif type(tgnames)==type([]):
			pass
		else:
			raise ValueError("`targets` argument should be a string or string-array that identifies some logging target(s).")

		invalid_tgs = set(tgnames) - set(self.__targets)
		if(invalid_tgs != set()):
			raise ValueError("`targets` argument contains invalid values: %s"%(",".join(invalid_tgs)))

		levelstr = ""
		if self.need_levelname:
			if sourcelevel in self.__level2name.keys():
				levelstr = "[%s]" % (self.__level2name[sourcelevel])

		msg_final = "[%s]%s%s\n" % (self.datetime_str(), levelstr, msg)

		for tgname in tgnames:
			target = self.__targets[tgname]
			if target.sinklevel < sourcelevel:
				continue
			target.logcall(msg_final)


if __name__=='__main__':

	def print1(s): print("!!%s"%(s), end='')
	def print2(s): print("##%s"%(s), end='')

	mtl = MTLog(need_millisec=True, need_levelname=True)
	mtl.add_target('ERROR', 1, print1)
	mtl.add_target('WARN', 2, print2)
	mtl.add_target('INFO', 5, print2)

	mtl.log(1, "an error message")
	print("")
	mtl.log(2, "an warning message")
	print("")
	mtl.log(3, "an info message") # this will not print [INFO] prefix, due to 5!=3
	print("")
	time.sleep(0.1)
	mtl.log(1, "2nd error message", targets='ERROR')
