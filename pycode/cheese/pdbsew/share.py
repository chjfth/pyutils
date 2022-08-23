#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, sys, time, subprocess
import math
import re
import datetime
import shlex
import glob
from enum import Enum,IntEnum # since Python 3.4
from subprocess_tools import pipe_process_with_timeout

FILENAME_CAPTURE_INI = 'pdbsew.capture.ini'

INDENT1 = " "*4

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


def prn(msg):
	print(msg)

def prnerr(msg):
	print("!!! TODO !!!");
	pass

def run_child_process_with_timeout(shellcmd,
		timeout_once_sec=0, timeout_total_sec=0,
		pipe_encoding=None):

	# DISCUSS: Can shellcmd contain pipe(|) or redirection(>), or ENVVAR=val prefix?
	# Perhaps not! TODO: check for bad input shellcmd format.

	cmdargs = shlex.split(shellcmd)
	exename = cmdargs[0]

	try:
		subproc = subprocess.Popen(cmdargs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	except FileNotFoundError:
		prn(f"[ERROR] The command to execute is not found: {exename}")
		exit(1)
	except OSError:
		print(f"[ERROR] Execution fail, perhaps not an executable file: {exename}")
		exit(1)

	with subproc:
		with pipe_process_with_timeout(subproc, once_secs, total_secs, is_print_dbginfo=True) as watchdog:
			for linebytes in subproc.stdout:
				if not linebytes:
					break
				print("###%s"%(linebytes.decode('utf8')), end='')
				watchdog.feed_dog()

	print("subproc.returncode=%d"%(subproc.returncode))


def svn_checkout_wrapper(svncmd):
	timeout_once_sec = 10
	timeout_total_sec = 300
	prn(f"Running svn checkout command:\n"
	    f"{INDENT1}     CMD: {svncmd}\n"
	    f"{INDENT1} timeout: once {timeout_once_sec} sec, total {timeout_total_sec} sec."
	    )

	exename = svncmd.split()[0]



if __name__=='__main__':
	pass
