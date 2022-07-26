#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, sys, time, subprocess
import math
import re
import datetime
import glob
from enum import Enum,IntEnum # since Python 3.4
from subprocess_tools import pipe_process_with_timeout

FILENAME_CAPTURE_INI = 'pdbsew.capture.ini'

class MsgLevel(IntEnum):
	err = 1
	warn = 2
	info = 3
	dbg = 4

def print_nolf(msg):
	print(msg, end='')

class Err_pdbsew(Exception):
	def __init__(self, errmsg, errcode=-1):
		self.errcode = errcode
		self.errmsg = errmsg
	def __str__(self):
		return self.errmsg

class Err_svn_exec(Err_pdbsew):
	def __init__(self, exitcode):
		errmsg = "svn subprocess execution error, exitcode=%d."%(exitcode)
		super().__init__(errmsg)


if __name__=='__main__':
	pass
