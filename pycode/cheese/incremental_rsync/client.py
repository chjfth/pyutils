#!/usr/bin/env python3
# coding: utf-8

# print("[%s] __name__=%s"%(__file__,__name__))

import os, sys, re
import time, datetime
import shutil, shlex
import traceback
from pathlib import Path
from enum import Enum,IntEnum # since Python 3.4
from collections import namedtuple

from cheese.filelock.assistive_filelock import AsFilelock, Err_asfilelock

from .share import *
from .helper import *

LOG_NOD = '__logs__' # as directory node name for storing log files.

ININAM_irsync_master = 'irsync.ini'
INISEC_last_success_dirpath = 'last_success_dirpath'
#
ININAM_sess_done = 'backup_done.ini'
INISEC_sess_done = 'backup_done'
INIKEY_utc = 'utc'
INIKEY_localtime = 'localtime'

def check_rsync_params_conflict(rsync_raw_params):
	# yes, irsync_args not used
	conflicts = (
		'--compare-dest', # would cause existing files in old-backup-dir to not appear in new-backup-dir.
	    '--copy-dest',
	    '--link-dest',  # this is set by irsync automatically
	    )
	clist = []
	for conflict in conflicts:
		if conflict in rsync_raw_params:
			clist.append(conflict)
	if clist:
		raise Err_irsync("Error: The following rsync native parameters are not allowed for irsync operation: %s"%(
			' , '.join(clist)
		))

def value_not_negative(irsync_args, argname, argval):
	if argval<0:
		raise Err_irsync("Error: The parameter(%s) must not be a negative value(%d)."%(argname, argval))

class irsync_st:

	pfxMsgLevel = [""]*5
	pfxMsgLevel[MsgLevel.err.value] = "[ERROR]"
	pfxMsgLevel[MsgLevel.warn.value] = "[WARN]"
	pfxMsgLevel[MsgLevel.info.value] = "[INFO]"
	pfxMsgLevel[MsgLevel.dbg.value] = "[DBG]"
	
	datetime_pattern_default = "YYYYMMDD"
	
	def _nouse_save_extra_args(self, args, argname, selfattr_desiredtype, selfattr_name, fn_check_valid=None, *fn_args):
		""" Search args[] for a param named argname. If found, validate it and save it as self's attribute.

		:param args: User input params, a dict. There may be valid ones and invalid ones.

		:param argname: an Irsync parameter name spec.
		:param selfattr_desiredtype: Desired/Valid type for the `argname`.

		:param selfattr_name:  For the `argname`, what attribute should we set for it.

		:param fn_check_valid: the function to validate `argname`'s value
		:param fn_args: Extra params passed to fn_check_valid()

		:return: On error, raise some exception
		"""
		if argname in args:
			argval = args[argname]
			if type(argval) != selfattr_desiredtype: # check argument type validity
				raise Err_irsync("You passed a wrong type to irsync initializing parameter '%s'. Desired type is '%s'."%(
					argname, 
					"%s.%s"%(selfattr_desiredtype.__module__, selfattr_desiredtype.__name__) # sample: cheese.incremental_rsync.client.MsgLevel
					))
			if fn_check_valid:
				fn_check_valid(args, argname, argval, *fn_args) # if error, should raise exception inside

			# This argument is ok, set it as object attribute.
			setattr(self, selfattr_name, argval)
		else:
			# Set default values for various types
			if selfattr_desiredtype==int:
				setattr(self, selfattr_name, 0)
			elif selfattr_desiredtype==str:
				setattr(self, selfattr_name, '')

	@property
	def master_logfile(self):
		return os.path.join(self.local_store_dir, "irsync.log")

	@property
	def master_logfile_lck(self):
		return self.master_logfile + ".lck"

	@property
	def sess_logfile_success(self):
		return self.sess_logfile.replace(self.working_dirpath, self.finish_dirpath)

	@property
	def ini_filepath(self):
		return os.path.join(self.local_store_dir, ININAM_irsync_master)

	@property
	def sess_done_ini_filepath(self):
		return os.path.join(self.working_dirpath, ININAM_sess_done)

	@property
	def finish_dirpath_rela(self):
		return str( Path(self.finish_dirpath).relative_to(self.local_store_dir) )

	def abspath(self, rela_path):
		"""Prefix local_store_dir to rela_path so to make an absolute dir."""
		return os.path.join(self.local_store_dir, rela_path)

	#def __init__(self, rsync_url, local_store_dir, local_shelf="", datetime_pattern="", **args):
	def __init__(self, apargs, rsync_extra_params):

		# apargs is the argparse.ArgumentParser object that accommodates all user parameters.
		#
		# [local_store_dir]/[datetime_vault]/[server.local_shelf] becomes final target dir for rsync.
		# [server.local_shelf] is called [ushelf] for brevity.

		self.uesec_start = uesec_now()

		#
		# Set some default working parameters.
		#
		
		self.rsync_url = apargs.rsync_url
		self.local_store_dir = os.path.abspath(apargs.local_store_dir)
		local_shelf = apargs.shelf # tune later
		self.datetime_pattern = apargs.datetime_pattern if apargs.datetime_pattern else __class__.datetime_pattern_default

		if self.datetime_pattern.find(' ')>=0:
			raise Err_irsync("Error: You assign datetime_pattern='%s', which contains space."%(self.datetime_pattern))

		#
		# Process extra optional arguments
		#
		self._loglevel = MsgLevel[apargs.msg_level]
		self._old_seconds = DHMS_to_Seconds(apargs.old_days, apargs.old_hours, apargs.old_minutes)
		self._max_retry = apargs.max_retry
		self._max_rsync_seconds = DHMS_to_Seconds(0, apargs.max_rsync_hours, apargs.max_rsync_minutes, apargs.max_rsync_seconds)
		self._max_irsync_seconds = DHMS_to_Seconds(0, apargs.max_irsync_hours, apargs.max_irsync_minutes, apargs.max_irsync_seconds)
		if self._max_irsync_seconds>0:
			#self.is_run_time_limit = True
			self.uesec_limit = uesec_now()+self._max_irsync_seconds
		else:
			#self.is_run_time_limit = False
			self.uesec_limit = 0
		#
		self._finish_dir_filename = apargs.finish_dir_filename
		self._finish_dir_relative = apargs.finish_dir_relative
		#
		self._rsync_extra_params = rsync_extra_params
		check_rsync_params_conflict(rsync_extra_params)

		#
		# prepare some static working data
		#
		
		# combine server-name and shelf-name into `ushelf` name (货架标识符).
		# 'u' implies unique, I name it so bcz I expect/hope it is unique within 
		# a specific local_store_dir .
		server, spath = _check_rsync_url(self.rsync_url)
		server_goodchars = server.replace(':', '~') # ":" is not valid Windows filename, so change it to ~

		if not local_shelf:
			local_shelf = spath.rstrip("/").split("/")[-1] # final word of spath

		# TODO: ensure no / in shelf name

		self.ushelf_name = "%s.%s"%(server_goodchars, local_shelf)
		
		# datetime_vault: this backup session's datetime-identified vault
		# Examples: 
		#		20200411.213300
		#		2020-04-11
		#
		self.datetime_vault = datetime_by_pattern(self.datetime_pattern)
		
		self.finish_dirpath = os.path.join(self.local_store_dir, self.datetime_vault, self.ushelf_name)
			# Final backup content will be placed in this dirpath. 
			# The dirpath consists of three parts:
			# local_store_dir / datetime_vault / ushelf_name

		# Backup content transferring is first stashed into a .working folder, and upon transfer finish,
		# it will then be moved to its finish_dirpath, for the purpose of being atomic.
		# Memo: I place .working folder directly at local_store_dir(instead of in datetime_vault subfolder)
		# for easy eye-catching.
		#
		self.working_dirname = "{0}[{1}].working".format(self.datetime_vault, self.ushelf_name)
		self.working_dirpath = os.path.join(self.local_store_dir, self.working_dirname)
		
		# Previous-backup info enable us to do incremental backup.
		#
		self.prev_ushelf_inifile = os.path.join(self.local_store_dir, "[{}].prev".format(self.ushelf_name))

		try:
			os.makedirs(self.local_store_dir, exist_ok=True)
			os.chdir(self.local_store_dir)
		except OSError:
			raise Err_irsync('Error: Cannot create/enter local_store_dir "%s"'%(self.local_store_dir))

		self.master_logfile_start()
		return

	def master_logfile_start(self):
		#
		# Acquire master-logfile's filelock first, so to ensure we're the only process
		# that is storing into this local_store_dir. If acquire-filelock fails, just quit.
		#
		self.master_filelock = AsFilelock(self.master_logfile_lck)

		try:
			self.master_filelock.lock()
		except Err_asfilelock as e:
			# We have no logfile to write here, so just print to stderr.
			# Translate to Err_irsync exception
			raise Err_irsync("""Error:  Cannot acquire lock on local_store_dir "%s", so I cannot continue.      
    Detail: %s
"""%(self.local_store_dir, e.errmsg))

		self.master_logfh = open(self.master_logfile, "a")
		self.master_logfh.write("\n"+ "~"*78 +"\n") # We don't want timestamp on this linesep char

		self.prn_masterlog("""Irsync session start.
    rsync_url:                {}
    local_store_dir(working): {}
    local_store_dir(finish) : {}
""".format  (
            self.rsync_url,
            self.working_dirpath,
            self.finish_dirpath
		    )
		)
		return

	def master_logfile_end(self, is_succ):

		uesec_end = time.time()
		run_seconds = int(uesec_end - self.uesec_start)

		runtime = "(Run-time: %d seconds =%dh,%dm,%ss)"%(run_seconds, *Seconds_to_DHMS(run_seconds)[1:4])

		if is_succ:
			if hasattr(self, 'sess_logfile'): # implies validity of .sess_logfile_success
				self.prn_masterlog("""Irsync session success. 
    Get your backup at:
        %s
    Session log file  :
        %s"""%(self.finish_dirpath, self.sess_logfile_success))

			self.prn_masterlog('Irsync session success. %s'%(runtime))
		else:
			self.prn_masterlog('Irsync session fail. %s'%(runtime))

		self.master_filelock.unlock()
		self.master_logfh.close()

	def log_finalize_due_to_exception(self):
		exctype, excvalue, _ = sys.exc_info()

		re_raise = True
		if issubclass(exctype, Err_irsync):
			# For our explict Err_irsync class, comprehensive error info should have been printed,
			# so no need to dump the mystic Python call-stack in whole.
			re_raise = False
		else:
			excpt_text = traceback.format_exc()
			self.prn_masterlog(excpt_text)

		self.prn_masterlog("""Irsync session stopped due to error/exception above! 
    Check session logfile at:
        %s
    Partial backup may be found at:
        %s""" % (self.sess_logfile, self.working_dirpath))

		self.master_logfile_end(False)
		return re_raise

	@property
	def loglevel(self):
		return self._loglevel
	
	@loglevel.setter
	def loglevel(self, level):
		self._loglevel = level

	def create_logfile(self):
		filename_pattern = "%s.run*.log"%(self.datetime_vault)
		filepath_pattern = os.path.join(self.working_dirpath, LOG_NOD, filename_pattern)
		fp, fh = create_logfile_with_seq(filepath_pattern) # in share.py
		return fp, fh

	def prn(self, msglevel, msg):

		self.lastlog_datetime_str = datetime_str_now(msec=True, compact=True)

		if self.loglevel.value < msglevel.value:
			return

		lvn = msglevel.value
		lvs = __class__.pfxMsgLevel[lvn]
		
		msgline = "[%s]%s %s\n"%(self.lastlog_datetime_str, lvs , msg)
		
		self.sess_logfh.write(msgline)
		print(msgline, end="")

	def err(self, msg):
		self.prn(MsgLevel.err, msg)
		raise Err_irsync(msg) # On err, we raise Exception to conclude our work.

	def warn(self, msg):
		self.prn(MsgLevel.warn, msg)

	def info(self, msg):
		self.prn(MsgLevel.info, msg)

	def dbg(self, msg):
		self.prn(MsgLevel.dbg, msg)

	def prn_masterlog(self, msg):
		msgline = "[%s]%s\n" % (datetime_str_now(msec=True, compact=True), msg)

		self.master_logfh.write(msgline)
		self.master_logfh.flush()

		print(msgline, end="")

	def prn_start_info(self):
		pass

	def sess_done_write_timestamp(self):
		uesec = int(time.time())
		tmlocal = time.localtime(uesec)
		localtime_str = time.strftime("%Y-%m-%d %H:%M:%S", tmlocal)

		ini_content = [
			(INIKEY_utc, str(uesec)),
			(INIKEY_localtime, localtime_str)
		]
		for t in ini_content:
			WriteIniItem(self.sess_done_ini_filepath, INISEC_sess_done, t[0], t[1])

	def y_find_existing_ushelf(self):
		# A backup_done.ini file identifies a ushelf directory.
		# And, I will check backup_done.ini only in second-depth subdirs.
		root_start = self.local_store_dir
		for root, dirs, files in os.walk(root_start):
			dirnods = root.replace(root_start, '', 1) # strip root_start prefix
#			print('dirnods='+dirnods) # debug
			if(dirnods.count(os.sep)==2):
				# now we are at the a second-depth subdir
				if ININAM_sess_done in files:
					uesec_str = ReadIniItem(os.path.join(root, ININAM_sess_done),
					                        INISEC_sess_done, INIKEY_utc)
					try:
						uesec = int(uesec_str)
#						print("%d @ %s" % (uesec, root)) # debug
						yield uesec, root
					except ValueError:
						pass # ignore it

				dirs.clear()    # so will not descend any further

	def remove_old_ushelfs(self):
		sec_keep = self._old_seconds
		if sec_keep<=0:
			return

		self.prn_masterlog("User requests removing backups older than %d days, %d hours, %d minutes."%(
			Seconds_to_DHMS(sec_keep)[0:3]
		))

		# Special: For dirpaths recorded in [last_success_dirpath], I will not remove them even if "outdated",
		# bcz they are precious for later incremental backups.
		#
		last_success_dirpaths = IniEnumSectionItems(self.ini_filepath, INISEC_last_success_dirpath)

		delete_count = 0
		uesec_new = int(time.time())
		for uesec_old, dirpath_old in self.y_find_existing_ushelf():
			sec_stale = uesec_new - uesec_old
			if sec_stale > sec_keep:
				str_DHM = "{} days, {} hours, {} minutes".format(*Seconds_to_DHMS(sec_stale)[0:3])

				if dirpath_old in last_success_dirpaths:
					self.prn_masterlog("""Seeing old backup at: (created %s ago (%d seconds stale))
    %s
--but do not remove it because it is recorded in %s as last-success (precious for later incremental backup)."""%(
						str_DHM, sec_stale,
						dirpath_old,
						ININAM_irsync_master
					))
				else:
					self.prn_masterlog("""Removing old backup at: (created %s ago (%d seconds stale))
    %s"""%(str_DHM, sec_stale, dirpath_old))

					shutil.rmtree(dirpath_old)
					delete_count +=1
					RemoveDir_IfEmpty(dirpath_old)

		if delete_count==0:
			self.prn_masterlog("No backups are stale, leaving them alone this time.")


	def run_irsync_session_once(self):
		"""
		Return normally on success, raise Exception on error.
		"""

		# Check whether finish-dirpath has existed, if so, the backup has done already.
		
		if os.path.exists(self.finish_dirpath):
			if os.path.isdir(self.finish_dirpath):
				self.prn_masterlog(
					"The local_store_dir(finish) has existed already. So I think the backup had been done some time ago.")
				return
			else:
				self.err("I need to create backup directory '%s', but it appears to be a file in the way."%(
					self.finish_dirpath))

		self.remove_old_ushelfs()

		# Create session logging filename and save its handle. If error, raise exception.
		#
		try:
			self.sess_logfile, self.sess_logfh = self.create_logfile()
			sesslog_d, sesslog_n = os.path.split(self.sess_logfile)
			assert( sesslog_d.startswith(self.working_dirpath) ) # sesslog_d has an extra 'logs' subdir
			self.prn_masterlog("""Session logfile can be found at:
    (working) : {}
    (finish)  : {}
""".format      (
				self.sess_logfile,
				self.sess_logfile_success
				)
			)
		except:
			# todo:: in the future, may employ a more detailed error message stack.
			self.prn_masterlog("Unexpected! Fail to create a session logfile.")
			raise

		self.info("irsync session - run() start")

		# Check whether last-success dir exists
		#
		last_succ_dirpath = ReadIniItem(self.ini_filepath, INISEC_last_success_dirpath, self.ushelf_name)
		if last_succ_dirpath:
			if os.path.isdir(last_succ_dirpath):
				self.info('Accelerate with last-success dirpath: "%s"'%(last_succ_dirpath))
			else:
				self.warn('INI recorded last-success dirpath NOT exists: "%s"'%(last_succ_dirpath))
				last_succ_dirpath = ""

		os.makedirs(self.working_dirpath, exist_ok=True)

		now_retry = 0
		while True:
			try:
				self.call_rsync_subprocess_once(last_succ_dirpath)
				break # bcz we succeeded
			except Err_rsync_exec:
				now_retry += 1

				if now_retry > self._max_retry:
					if self._max_retry > 0:
						self.warn("The rsync retrying count %d all exhausted."%(self._max_retry))
					raise # failure

				self.warn("Retrying rsync subprocess %d/%d ..."%(now_retry, self._max_retry))
				time.sleep(1.0)


		self.sess_logfh.close()
		self.sess_logfh = None

		self.sess_done_write_timestamp()

		try:
			os.makedirs(os.path.dirname(self.finish_dirpath), exist_ok=True) # create its parent dir
			os.rename(self.working_dirpath, self.finish_dirpath) # move and rename the dir
		except OSError:
			raise Err_irsync("Error: Irsync session succeeded, but fail to move working directory to finish directory.")

		# Record [last_success_dirpath] into rsync.ini
		try:
			WriteIniItem(self.ini_filepath, INISEC_last_success_dirpath,
		             self.ushelf_name, self.finish_dirpath_rela)
		except OSError:
			raise Err_irsync('Error: Cannot record [%s] information into file "%s"'%(
				INISEC_last_success_dirpath, self.ini_filepath))
		return

	def call_rsync_subprocess_once(self, last_succ_dirpath):

		now = uesec_now()
		if self.uesec_limit>0 and now>=self.uesec_limit:
			self.err("""The rsync subprocess will not run, due to irsync session time limit({} hours, {} minutes, {} seconds).""".format(
				*Seconds_to_DHMS(self._max_irsync_seconds)[1:4]
			))
			raise Err_irsync("Irsync session fail, due to session time limit.")

		rsync_run_secs = self._max_rsync_seconds
		if self.uesec_limit>0:
			rsync_run_secs = min(self._max_rsync_seconds, self.uesec_limit-now)

		line_sep78 = '=' * 78
		#
		# Prepare rsync subprocess parameters...
		# and we'll use argv[] to spawn subprocess, not bothering sh/bash command line.
		#
		rsync_argv = ["rsync", "-av"]

		if last_succ_dirpath:
			# No need to surround the path with quotes, even if it contains spaces, bcz we will use shell=False.
			# And we must pass abspath to --link-dest= bcz relative path means differently to rsync.
			rsync_argv.append('--link-dest=%s' % (self.abspath(last_succ_dirpath)))

		if self._rsync_extra_params:
			rsync_argv.extend(self._rsync_extra_params)

		# Finally, append rsync-source and rsync-destination
		rsync_argv.extend([self.rsync_url, self.working_dirpath])

		# Create logfile for rsync-subprocess's console output message.
		#
		# If irsync session logfile(self.sess_logfile) is 20200414.run0.log,
		# We will create rsync logfile with pattern 20200414.run0.rsync*.log ,
		# so that we know the "...rsync0.log", "...rsync1.log" belongs to run0.
		#
		rsync_logfile_pattern = '.rsync*'.join(os.path.splitext(self.sess_logfile))
		fp_rsync, fh_rsync = create_logfile_with_seq(os.path.join(self.working_dirpath, rsync_logfile_pattern))

		# Construct subprocess startup log text:
		argv_hint_lines = ["{0}argv[{1}] = {2}".format(' ' * 8, i, s) for i, s in enumerate(rsync_argv)]
		shell_cmd = ' '.join([shlex.quote(onearg) for onearg in rsync_argv])
		self.info("""Launching rsync subprocess with argv[]:
%s
    The corresponding shell command line is (for your manual debugging):
	    %s
    With log file: %s (in same directory as this one)
    This rsync run-time limit: %s
%s
""" % (
			'\n'.join(argv_hint_lines),
			shell_cmd,
			os.path.basename(fp_rsync),
			Seconds_to_HMS_string(rsync_run_secs),
			line_sep78))
		#
		# Add some banner text at start of fp_rsync.
		fh_rsync.write("""[%s] This is the console output log of shell command:
    %s
%s
""" % (self.lastlog_datetime_str, shell_cmd, line_sep78))
		#
		(exitcode, kill_at_uesec) = run_exe_log_output_and_print(
			rsync_argv, rsync_run_secs, {"shell": False}, fh_rsync)

		if exitcode == 0:
			self.info("rsync run success.")
		else:
			if kill_at_uesec > 0:
				kill_msg = "rsync max run-time limit exceeded. Kill signal has been issued at %s ." % (
					datetime_str_by_uesec(kill_at_uesec)
				)
				self.warn(kill_msg)

			# Use warn(instead of error) here, bcz I do not consider it the FINAL error.
			#
			self.warn("""rsync run fail, exitcode=%d
    To know detailed reason. Check rsync console message log at:
        %s""" % (exitcode, fp_rsync))

			raise Err_rsync_exec(exitcode, self.ushelf_name)  # The caller may retry rsync.exe later

		self.info("irsync session - run() end")

		# Move .working-directory into finish-directory
		#
		fh_rsync.close()

	def success_cleanup(self):
		if self._finish_dir_filename:
			hint_fp = os.path.abspath(self._finish_dir_filename)
			hint_text = self.finish_dirpath
			if self._finish_dir_relative:
				hint_text = self.finish_dirpath_rela

			succ = True
			try:
				open(hint_fp, "w").write(hint_text)
			except:
				succ = False

			self.prn_masterlog("""Write finish directory to file:
    %s
-- %s """%(
				hint_fp,
				"Success." if succ else "Fail!"
            ))
		self.master_logfile_end(True)
		return

def _check_rsync_url(rsync_src):
	"""Check rsync url format validity.

	Two forms are valid:
	1.
		rsync://<server>/<srcmodule>
		rsync://<server>/<srcmodule>/dirname
		rsync://<server>/<srcmodule>/dirname/
	2.
		/home/userfoo/myrepo
		/home/userfoo/myrepo

	Whether the url should end with a slash is solely the user's preference, and the trailing slash
	is passed to rsync exe without modification.
	You know, rsync will behave slightly differently with or without the trailing slash.
	"""

	if rsync_src.strip('/')=='':
		raise Err_irsync("Error: rsync url cannot be a single / .")

	m1 = re.match("rsync://([^/]+)/(.+)", rsync_src)
	m2 = os.path.isabs(rsync_src)
	if m1:
		# return (server-name, server-path)
		return m1.group(1), '/'+m1.group(2)
	elif m2:
		return 'LOCALHOST', rsync_src
	else:
		raise Err_irsync("Error: Wrong rsync url format: %s" % (rsync_src))
	


def irsync_fetch_once(apargs, rsync_extra_params):

	try:
		irs = irsync_st(apargs, rsync_extra_params)
	except Err_irsync as e:
		print(e.errmsg)
		return False

	try:
		irs.run_irsync_session_once()
		irs.success_cleanup()
	except:
		re_raise = irs.log_finalize_due_to_exception()
		if re_raise:
			raise
		else:
			return False

	return True
	
