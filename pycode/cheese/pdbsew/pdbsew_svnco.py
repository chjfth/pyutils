#!/usr/bin/env python3
# coding: utf-8


import os, sys
import re, time
import configparser
import argparse
from .share import *

def non_negative_int(x):
	i = int(x)
	if i < 0:
		raise argparse.ArgumentTypeError('Negative values are not allowed.')
	return i

def init_argparser():
	ap = argparse.ArgumentParser(
		description="pdbsew-svnco, SVN checkout command wrapper for pdbsew. "
		            "This wrapper records assistive files in your checkout local folder so that pdbsewing "
					"may take effect in following developing cycle."
	)

	ap.add_argument('svnurl', type=str,
		help='The SVN URL to checkout, sth like: svn://server.com/svnrepo/somelib .'
	)

	ap.add_argument('-t', '--svnco-datetime', type=str, default='', dest='svnco_datetime',
		help='The datetime to checkout. Complete foramt is like:\n'
			 '  "2022-07-25 18:30:00 +0800" \n'
		     'or, to avoid space-char,\n'
			 '   2022-07-25.18:30:00.+0800 \n'
	         'If you omit timezone, client machine timezone is used.'
	) # long option is named "svnco-datetime" bcz its value is passed directly to 'svn checkout'

	ap.add_argument('-d', '--localdir', type=str, default='',
		help='Checkout to which local folder, default to current working directory.'
	)

	ap.add_argument('-b', '--branchie', type=str, default='',
		help='The branchie string is the path node(s) that signify a branch in svn url. '
	        'If omitted(by default), it is determined automatically. Default rule is:\n\n'
	        'If there is "/trunk/sth1" in url, "trunk" is considered the branchie.\n\n'
		    'If there is "/tags/sth2/sth3" in url, "tags/sth2" is considered the branchie.\n'
		    'If there is "/branches/sth4/sth5" in url, "branches/sth4" is considered the branchie.\n'
		    'If its value is a single "/", then it explicitly means no branchie.\n'
	        'Purpose: When pdbsew later does revive-checkout, the branchie part will not appear in local dir.'
	)

	ap.add_argument('--msg-level', type=str, dest='msg_level', choices=[e.name for e in list(MsgLevel)],
		default='info',
		help='Assigns log message level. Default is "%(default)s".'
	)

	return ap

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

def capture_by_svnurl(apargs):
	"""Capture an svnurl state according to input svnurl and datetime.

	Input: [apargs] .svnurl .svnco_datetime .localdir

	Output: $(.localdir)/pdbsew.capture.ini
	"""
	svnco_datetime = normalize_svnco_datetime(apargs.svnco_datetime)

	# apargs.svnco_datetime
	apargs.svnco_datetime = svnco_datetime

	# apargs.localdir
	if apargs.localdir == '':
		apargs.localdir = os.getcwd()

	# SVN URL dissection: svn://servername.com:3690/svnrepo/repo1/tags/v1.0/feature1
	# urlbase  = svn://servername.com:3690
	# urlhost  = servername.com~3690
	# urlpathF = /svnrepo/repo1/tags/v1.0/feature1  (F implies fullpath)
	# urlpathA = svnrepo/repo1
	# urlpathB = tags/v1.0
	# urlpathC = feature1

	# Extract urlbase.
	#
	r = re.match(r'([a-z+]+://([a-z0-9-_@.:]+))/', apargs.svnurl)
	if not r:
		raise Err_pdbsew('svnurl format error: No valid "scheme" found in ("%s")' % (apargs.svnurl))

	urlbase = r.group(1)  # no trailing slash
	urlhost = r.group(2).replace(':', '~')  # would be disk folder name

	urlpathF = apargs.svnurl[len(urlbase):]

	# Extract urlpathA/B/C
	urlpathA = urlpathF.lstrip('/')  # for the case of input branchie="/" (explicit no branchie)
	urlpathB = urlpathC = ''
	#
	if apargs.branchie == "":
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

			apargs.branchie = urlpathB
		else:
			pass  # leave the branchie blank

	elif apargs.branchie == "/":
		apargs.branchie = ""
		pass  # urlpathA/B/C defaults already set
	else:
		# User explicit branchie, and we need to actually see that branchie in svnurl.
		r = re.match(r'(.*?)(/%s)(/.*)*' % (apargs.branchie), urlpathF)
		if r:
			urlpathA = r.group(1).lstrip('/')
			urlpathB = r.group(2).lstrip('/')
			if r.group(3):  # may be None
				urlpathC = r.group(3).lstrip('/')
		else:
			raise Err_pdbsew('svnurl error: You assign branchie="%s", but that string does not exist in svnurl("").' % (apargs.branchie, apargs.svnurl))

		assert apargs.branchie != ""

	# apargs.branchie set [above]

	svnco_capture_exec = 'svn co %s@"{%s}" %s'%(
		'/'.join([urlbase, urlpathA, urlpathB, urlpathC]),
		apargs.svnco_datetime,
		apargs.localdir)

	INISECT = 'svninfo'

	iniobj = configparser.ConfigParser()
	if not iniobj.has_section(INISECT):
		iniobj.add_section(INISECT)

	iniobj.set(INISECT, 'svnurl', apargs.svnurl)
	iniobj.set(INISECT, 'branchie', apargs.branchie)
	iniobj.set(INISECT, 'svnco_datetime', apargs.svnco_datetime)
	iniobj.set(INISECT, 'localdir', apargs.localdir)
	iniobj.set(INISECT, 'svnco_capture_exec', svnco_capture_exec)

	iniobj.set(INISECT, 'urlbase', urlbase)
	iniobj.set(INISECT, 'urlhost', urlhost)
	iniobj.set(INISECT, 'urlpathF', urlpathF)
	iniobj.set(INISECT, 'urlpathA', urlpathA)
	iniobj.set(INISECT, 'urlpathB', urlpathB)
	iniobj.set(INISECT, 'urlpathC', urlpathC)

	fpath_capture_ini = os.path.join(apargs.localdir, FILENAME_CAPTURE_INI)
	with open(fpath_capture_ini, 'w') as fh:
		iniobj.write(fh)

	return


def do_cmd():
	"""Command line interface, will use sys.argv[] implicitly. """

	# Warn empty parameter and quit.
	#
	ap = init_argparser()
	if len(sys.argv)==1:
		ap.print_usage()
		exit(1)

	argv = sys.argv

	apargs = ap.parse_args(argv[1:])

	capture_by_svnurl(apargs)

	print("====ok====")
	print(apargs)

	return 0

if __name__ == '__main__':

	err = do_cmd()

	exit(err)
