#!/usr/bin/env python3
# coding: utf-8

"""
D:\gitw\pyutils> python -m cheese.incremental_rsync.test
"""

import os, sys
import argparse
from .share import *
from .client import *
from .client import _check_rsync_url

def non_negative_int(x):
    i = int(x)
    if i < 0:
        raise argparse.ArgumentTypeError('Negative values are not allowed.')
    return i

def init_irsync_argparser():
	ap = argparse.ArgumentParser(description="irsync, the incremental rsync wrapper.")

	ap.add_argument('rsync_url', type=str,
		help='The rsync URL of your backup source, sth like: rsync://server/module/subdir .'
	)
	ap.add_argument('local_store_dir', type=str,
		help='Your local directory as backup destination. Sub-directories will be created within'
			 'automatically for each incremental backup. '
	         'That is, to backup the same source URL twice, you just pass in the same local store dir.'
	)
	ap.add_argument('shelf', type=str, nargs='?', default='',
		help='An optional shelf name. A shelf name identifies an asset of your backup source.\n'
		    'The shelf name will become the sub-directory name housing your backup files. '
			'If not given explicitly, irsync generates a shelf name according to rsync URL, '
	        'so that different URLs result in different shelf names.\n'
	        'If you assign shelf name manually and have two rsync URLs mapping to the same shelf name, '
	        'irsync will consider the two URLs belonging to same asset. That means, if you want one backup '
	        'each day, and URL1 has been backed-up today, then URL2 will not get backed-up today, because '
	        'irsync thinks that backup of that asset name has already been done today.'
	)

	ap.add_argument('--datetime-pattern', type=str, dest='datetime_pattern',
		help='This option determines the conceptual time point to which a backup is attached.\n'
	        'It is optional and defaults to "YYYYMMDD", where YYYY,MM,DD are replaced with current '
			'year,month,day respectively, to make a final datetime-result(FDT). \n'
	        'The same FDT represent the same conceptual time point. For the same FDT, the backup operation'
		    '(file transfer/copy) will be carried out only once. Even if you try it a second time, '
	        'irsync will tell you the backup has been done already. So, YYYYMMDD means one backup per day. '
	        'If you want a backup per minute, you can use YYYYMMDD-hhmm, where hh means hour, mm means minute.'
	        '(note the difference of MM and mm)'
	)

	ap.add_argument('--msg-level', type=str, dest='msg_level', choices=[e.name for e in list(MsgLevel)],
		default='info',
		help='Assigns log message level. Default is "%(default)s".'
	)

	ap.add_argument('--old-days', type=non_negative_int, dest='old_days', default=0,
		help='Tells how many days to keep old backups. If it is 30, then backups older than 30 days '
	         'will be automatically deleted. \n'
	         'This defaults to 0, means no auto-delete.'
	)
	ap.add_argument('--old-hours', type=int, dest='old_hours', default=0,
		help='Add extra hours to old days. This is mainly used for testing the auto-delete feature. \n'
	        'There is --old-minutes as well.'
	)
	ap.add_argument('--old-minutes', type=int, dest='old_minutes', default=0,
		help=argparse.SUPPRESS
	)

	ap.add_argument('--max-rsync-hours', type=non_negative_int, dest='max_rsync_hours', default=0,
		help='Assign max hours to run for one rsync subprocess execution.'
	        'Default value 0 means no time limit, and irsync will wait as long as rsync executes, '
	        'and as many times as --max-retry is specified.'
	)
	ap.add_argument('--max-rsync-minutes', type=int, dest='max_rsync_minutes', default=0,
		help='Add extra minutes to --max-rsync-hours, testing use. \n'
	        'There is --max-rsync-seconds as well.'
	)
	ap.add_argument('--max-rsync-seconds', type=int, dest='max_rsync_seconds', default=0,
		help=argparse.SUPPRESS
	)

	ap.add_argument('--max-retry', type=int, dest='max_retry', default=0,
		help='Assign max retry count for calling rsync subprocess. '
	        'Default is 0, meaning irsync will call rsync subprocess only once, no retry.'
	)

	ap.add_argument('--max-irsync-hours', type=non_negative_int, dest='max_irsync_hours', default=0,
		help='Assign max hours to run for a whole irsync session.\n'
	        'There is --max-irsync-minutes and --max-irsync-seconds for test purpose.'
	)
	ap.add_argument('--max-irsync-minutes', type=int, dest='max_irsync_minutes', default=0, help=argparse.SUPPRESS)
	ap.add_argument('--max-irsync-seconds', type=int, dest='max_irsync_seconds', default=0, help=argparse.SUPPRESS)

	ap.add_argument('--finish-dir-write-to', type=str, dest='finish_dir_filename',
	    help='This assign a filename. If backup success, the final backup directory(full-path) '
	        'will be written to this filename, so the caller can know it and do some post actions. '
	        'But if the backup fails, the original content of this filename will not be touched. '
	        'Sure, it can be a bare filename, or a filename with absolute/relative path prefix.'
	)
	ap.add_argument('--finish-dir-relative', action="store_true", dest='finish_dir_relative',
		help='Use with --fetch-finish-dir-from=<filename>. If present, the dirpath written to <filename> '
	        'will be a relative path to current working directory, if possible.'
	)

#	ap.add_argument('--rsync', type=str, dest='rsync_extra_params', nargs=argparse.REMAINDER,
#		help='Supply extra rsync parameters. \n'
#		    ' This option MUST appear finally on the command line, and its full content MUST not be wrapped by any quotes.'
#	)
	# -- [2020-08-12] Note: (python 3.7) nargs=argparse.REMAINDER works well, but I do not use it,
	# just bcz print_usage() is a bit buggy with it. The print_usage() hint does NOT list [--rsync ...] at tail, sigh.
	# ... instead:
	ap.add_argument('--rsync', action="store_true", # a tweak
	    help='Use [--rsync ... ] to pass any parameters verbatim to rsync subprocess, no extra quotation marks required.\n'
	        'IMPORTANT: You have to place these parameters at very tail of your whole command line so that '
	        'I can clearly tell them apart from irsync\'s own parameters.'
	)
	# This tells argparse to display help for --rsync for us, but I will process --rsync ... myself.
	# So using action="store_true" is enough.

	return ap

def irsync_cmd():
	"""Irsync command line interface, will use sys.argv[] implicitly. """

	# Warn empty parameter and quit.
	#
	ap = init_irsync_argparser()
	if len(sys.argv)==1:
		ap.print_usage()
		exit(1)

	#
	# First, scan for "--rsync ..." parameter from command line, and extract it.
	#

	argv = sys.argv
	rsync_extra_params = []

	try:
		idx_rsync = argv.index('--rsync')
		rsync_extra_params = argv[idx_rsync+1:] # copy all eles after the --rsync
		argv[idx_rsync:] = [] # trim all eles from after --rsync
	except ValueError:
		pass

	#
	# Second, use argparse API to parse remaining parameters
	#

	apargs = ap.parse_args(argv[1:])
	succ = irsync_fetch_once(apargs, rsync_extra_params)

	# ret = irsync_fetch_once(args.rsync_url, args.local_store_dir, args.shelf,
	# 	datetime_pattern=args.datetime_pattern,
	#     old_days=args.old_days,
	# 	old_hours=args.old_hours,
	# 	old_minutes=args.old_minutes,
	# 	max_retry=args.max_retry,
	# 	max_run_seconds=args.max_run_seconds,
	#     rsync_extra_params=rsync_extra_params)

	return succ

if __name__ == '__main__':

#	aptest()
	succ = irsync_cmd()

	exit(0 if succ else 4)
