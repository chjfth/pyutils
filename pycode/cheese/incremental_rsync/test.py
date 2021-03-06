#!/usr/bin/env python3
# coding: utf-8

"""
D:\gitw\pyutils> python -m cheese.incremental_rsync.test
"""

import os, sys
from .client import *
from .client import _check_rsync_url

# Would cause double-import warning! So comment out this following.
if __name__=='__main__':

#	server, path = _check_rsync_url("rsync://server/mod/SUB1")
#	print("server=%s , path=%s"%(server, path))

	ret = irsync_fetch_once("rsync://192.168.11.1:1873/mys", ".", "shelf1",
		datetime_pattern="YYYYMMDD-hhmmss",
		rsync_extra_params=["--progress"],
	    old_days=0, old_hours=0, old_minutes=10,
#		loglevel=11, #MsgLevel.warn,
		_=None)
	print(ret)
	
