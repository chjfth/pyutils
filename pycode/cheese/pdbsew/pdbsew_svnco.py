#!/usr/bin/env python3
# coding: utf-8


import os, sys
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

	ap.add_argument('-t', '--svnco_datetime', type=str, default='',
		help='The datetime to checkout. Complete foramt is like:\n'
			 '  "2022-07-25 18:30:00 +0800" \n'
	         'If you omit timezone, client machine timezone is used.'
	)
	ap.add_argument('-d', '--local_dir', type=str, default='',
		help='Checkout to which local folder, default to current working directory.'
	)

	ap.add_argument('--branchie', type=str, default='',
		help='The branchie string is the path node(s) that signify a branch in svn url. '
	        'If omitted(by default), it is determined automatically. Default rule is:\n'
	        'If there is "/trunk/sth1" in url, "/trunk" is considered the branchie.\n'
		    'If there is "/tags/sth2/sth3" in url, "/tags/sth2" is considered the branchie.\n'
		    'If there is "/branches/sth4/sth5" in url, "/branches/sth4" is considered the branchie.\n'
	        'Purpose: When pdbsew later does revive-checkout, the branchie part will not appear in local dir.'
	)

	ap.add_argument('--msg-level', type=str, dest='msg_level', choices=[e.name for e in list(MsgLevel)],
		default='info',
		help='Assigns log message level. Default is "%(default)s".'
	)

	return ap

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

	print("====ok====")
	print(apargs)

	return 0

if __name__ == '__main__':

	err = do_cmd()

	exit(err)
