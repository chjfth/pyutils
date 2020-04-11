#!/usr/bin/env python3
# coding: utf-8

"""
D:\gitw\pyutils> python -m cheese.incremental_rsync.test
"""

from .client import *
from .client import _check_rsync_url

# Would cause double-import warning! So comment out this following.
if __name__=='__main__':

#	server, path = _check_rsync_url("rsync://server/mod/SUB1")
#	print("server=%s , path=%s"%(server, path))

	ret = irsync_fetch_once("rsync://server/mod", "d:/test", "shelf1")
	print(ret)
	
