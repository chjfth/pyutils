#!/usr/bin/env python3
# coding: utf-8


import os, sys
import re, time
import configparser
import click
#import argparse
from .share import *

def local_timezone_minute_str():
	# For China, return "+0800"
	absminute = abs(time.timezone)/60
	s = '+' if time.timezone<=0 else '-'
	s += "%02d%02d"%(absminute/60, absminute%60)
	return s

def replace1char(instr, pos, newchar):
	return instr[:pos] + newchar + instr[pos+1:]

def normalize_svnco_datetime(dtstr):
	ymd = dtstr[0:10]
	if not re.match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', ymd):
		raise Err_pdbsew('svnco-datatime format error in year-month-day("%s")'%(ymd))

	sep1 = dtstr[10]
	if not sep1 in [' ', '.']:
		raise Err_pdbsew('svnco-datatime format error: There should be a separator(comma or dot) after year-month-day("%s")'%(ymd))

	hms = dtstr[11:19]
	if not re.match(r'[0-9]{2}:[0-9]{2}:[0-9]{2}', hms):
		raise Err_pdbsew('svnco-datatime format error in hour-minute-second("%s")' % (hms))

	sep2 = dtstr[19:20]
	if sep2 == '':
		# add local timezone
		dtstr += ' '+local_timezone_minute_str()
	else:
		if not sep2 in [' ', '.']:
			raise Err_pdbsew('svnco-datatime format error: There should be a separator(comma or dot) after hour-minute-secon("%s")' % (hms))

		tzstr = dtstr[20:]
		if not re.match(r'[+-][0-9]{4}', tzstr):
			raise Err_pdbsew('svnco-datatime format error in timezone("%s")' % (tzstr))

	# normalize separator to space-char, which is the correct format for svn.exe
	dtstr = replace1char(dtstr, 10, ' ')
	dtstr = replace1char(dtstr, 19, ' ')
	return dtstr


@click.command(name="capture")
@click.argument("svnurl", required=True)
@click.argument("localdir", required=False)
@click.option("-t", "timestamp", metavar="TIMESTAMP", help="""
	The datetime to checkout. Complete format is like:
	
	\b
	    2022-07-25 18:30:00 +0800
	
	\b
	or, to avoid space-char:
	
	\b
	    2022-07-25.18:30:00.+0800

	If you omit timezone, client machine timezone is used.

	\b
	""")
@click.option("-b", "branchie", help="""
	The branchie string is the path node(s) that signify a branch in svn url.

	\b
	If omitted, it is determined automatically. The rule is:
	- If "/trunk/sth1" in url, "trunk" is considered the branchie.
	- If "/tags/sth2/sth3" in url, "tags/sth2" is.
	- If "/branches/sth4/sth5" in url, "branches/sth4" is.

	If assigning value "/", then it explicitly means no branchie.

	Purpose: When pdbsew later does revive-checkout, the branchie part will not be created
	in your local file system.
	
	\b
	""")
def pdbsew_capture(svnurl, localdir, timestamp, branchie):
	"""Capture an svn-repo state according to an SVN URL and a timestamp.
	If timestamp is not explicitly assigned, current time will be used.

	If localdir is not explicitly assigned, current working dir is used.
	A file named pdbsew.capture.ini will be generated in LOCALDIR to record
	the captured state.

	The captured state will be later used by pdb-sewing procedure.

	SVNURL is the svn url used in `svn checkout` command. Example:

		svn://server.com/svnrepo/somelib

	LOCALDIR is your local file system directory, default to current working dir.

	\f

	:param svnurl:

	:param localdir:
	:param svnco_datetime:
	:param branchie:
	:return:
	"""

	svnco_datetime = normalize_svnco_datetime(timestamp)

	if not localdir == '':
		localdir = os.getcwd()

	# SVN URL dissection: svn://servername.com:3690/svnrepo/repo1/tags/v1.0/feature1
	# urlbase  = svn://servername.com:3690
	# urlhost  = servername.com~3690
	# urlpathF = /svnrepo/repo1/tags/v1.0/feature1  (F implies fullpath)
	# urlpathA = svnrepo/repo1
	# urlpathB = tags/v1.0
	# urlpathC = feature1

	# Extract urlbase.
	#
	r = re.match(r'([a-z+]+://([a-z0-9-_@.:]+))/', svnurl)
	if not r:
		raise Err_pdbsew('svnurl format error: No valid "scheme" found in ("%s")' % (svnurl))

	urlbase = r.group(1)  # no trailing slash
	urlhost = r.group(2).replace(':', '~')  # would be disk folder name

	urlpathF = svnurl[len(urlbase):]

	# Extract urlpathA/B/C
	urlpathA = urlpathF.lstrip('/')  # for the case of input branchie="/" (explicit no branchie)
	urlpathB = urlpathC = ''
	#
	if not branchie:
		# Search for conventional branchie in svnurl.
		r = re.match(r'(.*?)(/trunk)(/.*)*', urlpathF)
		if not r:
			r = re.match(r'(.*?)(/tags/[^/]+)(/.*)*', urlpathF)
		if not r:
			r = re.match(r'(.*?)(/branches/[^/]+)(/.*)*', urlpathF)

		if r:
			urlpathA = r.group(1).lstrip('/')
			urlpathB = r.group(2).lstrip('/')
			if r.group(3):  # may be None
				urlpathC = r.group(3).lstrip('/')

			branchie = urlpathB
		else:
			pass  # leave the branchie blank

	elif branchie == "/":
		branchie = ""
		pass  # urlpathA/B/C defaults already set
	else:
		# User explicit branchie, and we need to actually see that branchie in svnurl.
		r = re.match(r'(.*?)(/%s)(/.*)*' % (branchie), urlpathF)
		if r:
			urlpathA = r.group(1).lstrip('/')
			urlpathB = r.group(2).lstrip('/')
			if r.group(3):  # may be None
				urlpathC = r.group(3).lstrip('/')
		else:
			raise Err_pdbsew('svnurl error: You assign branchie="%s", but that string does not exist in svnurl("").' % (apargs.branchie, apargs.svnurl))

		assert branchie != ""

	# apargs.branchie set [above]

	svnco_capture_exec = 'svn co %s@"{%s}" %s'%(
		'/'.join([urlbase, urlpathA, urlpathB, urlpathC]),
		svnco_datetime,
		localdir)

	INISECT = 'svninfo'

	iniobj = configparser.ConfigParser()
	if not iniobj.has_section(INISECT):
		iniobj.add_section(INISECT)

	iniobj.set(INISECT, 'svnurl', svnurl)
	iniobj.set(INISECT, 'branchie', branchie)
	iniobj.set(INISECT, 'svnco_datetime', svnco_datetime)
	iniobj.set(INISECT, 'localdir', localdir)
	iniobj.set(INISECT, 'svnco_capture_exec', svnco_capture_exec)

	iniobj.set(INISECT, 'urlbase', urlbase)
	iniobj.set(INISECT, 'urlhost', urlhost)
	iniobj.set(INISECT, 'urlpathF', urlpathF)
	iniobj.set(INISECT, 'urlpathA', urlpathA)
	iniobj.set(INISECT, 'urlpathB', urlpathB)
	iniobj.set(INISECT, 'urlpathC', urlpathC)

	fpath_capture_ini = os.path.join(localdir, FILENAME_CAPTURE_INI)
	with open(fpath_capture_ini, 'w') as fh:
		iniobj.write(fh)

	return

if __name__ == '__main__':
	pdbsew_capture() # no return
