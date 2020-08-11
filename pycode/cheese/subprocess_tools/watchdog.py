import os, sys, time
import subprocess
from threading import Thread, Event, Lock
from contextlib import contextmanager


# @property
def now_tick_monotonic():
	now_tick_sec = time.monotonic()
	return now_tick_sec

# Idea from the WatchdogTimer class: https://stackoverflow.com/a/34115590/151453
#
class WatchdogThread(Thread):
	"""A WatchdogThread object represents a worker(dog) thread that periodically monitors main thread's activity,
	and if no activity is detected, the dog thread will take some specified action assigned by the user.

	If the main thread feeds the dog constantly and timely, the dog remains in peace and monitoring continues.
	But if the the main thread fails that, the dog thread will call a timeout-action, then the dog thread exits.

	User can also assign a max_run_seconds of the dog thread. When that max_run_seconds has elapsed,
	the timeout-callback will be called as well.

	[USAGE EXAMPLE]
	Before the main thread starts a blocking IO, sth like reading a pipe from a sub-process,
	the main thread can start a watchdog thread so to detect possible infinite blocking of that IO.
	If the main thread does not feed the dog timely, it means the main thread has blocked for a overly long time,
	so the dog thread will detect this timeout case and take action. That timeout-action was assigned by
	the main thread earlier when creating the WatchdogThread object, and the callback is typically
	Popen.kill() which would kill the stalled sub-process, and this, will typically bring the main thread
	out of the blocking state.
	.
	In the above example, the max_run_seconds will determine max run-time of the sub-process.
	"""

	def __init__(self, once_timeout_sec, max_run_seconds, timeout_action, *action_args,
	             is_print_dbginfo=False,
	             **thread_init_kwargs):
		"""Initialize the WatchdogThread object.

		:param once_timeout_sec:
			The dog feeding interval should not exceed this many seconds,
			otherwise, timeout action will be taken.
			If 0, once-timeout is not used, i.e. only use max_run_seconds.

		:param max_run_seconds:
			When these seconds has elapsed, timeout action will be taken.
			If 0, max_run_seconds is not used, i.e. only use once_timeout_sec.

		:param timeout_action:
			The callback function that represents a timeout-action.

		:param action_args:
			These arguments are passed to timeout_action when it is called.

		:param thread_init_kwargs:
			The keyword arguments to initialize the Thread object. Mostly used:
			name=... : Name the thread.
			daemon=True/False : Whether run the thread as a daemon.
		"""

		super().__init__(**thread_init_kwargs)

		# Create some supporting resources
		#
		self._mutex = Lock()
		self._evt_done = Event()

		# Init working params
		#
		self.set_new_timeout(once_timeout_sec, max_run_seconds)
		#
		self._timeout_action = timeout_action
		self._action_args = action_args

		self._is_print_dbginfo = is_print_dbginfo
		pass

	def set_new_timeout(self, once_timeout_sec, max_run_seconds=0):
		"""Update new timeout values

		:param once_timeout_sec: See __init__() .
		:param max_run_seconds: The seconds is calculated from now on, not from when the thread first starts.
		:return: None.
		"""

		with self._mutex:
			self._once_timeout_sec = once_timeout_sec
			self._is_once_timeout = True if once_timeout_sec > 0 else False

			self.__max_run_seconds = max_run_seconds # debug only
			if max_run_seconds>0:
				self._is_final_deadline = True
				self._final_deadline = now_tick_monotonic() + max_run_seconds
			else:
				self._is_final_deadline = False
				self._final_deadline = 0

	def feed_dog(self):
		if self._is_once_timeout:
			self._moving_deadline = now_tick_monotonic() + self._once_timeout_sec

			if self._is_print_dbginfo:
				print("WatchdogThread.feed_dog().")
		else:
			self._moving_deadline = 0 # not-used

	def work_done(self):
		"""Main thread calls this function to signify it has done its real work and
		 the watchdog is no longer needed. The monitoring dog thread will be signaled and quit.

		:return: None.
		"""
		if self._is_print_dbginfo:
			print("WatchdogThread.work_done().")

		self._evt_done.set()

	def run(self): # Override Thread.run()
		"""This is watchdog's thread code. It is started by main-thread calling threadobj.start() .

		:return: None, or timeout-action's return code.
		"""
		if self._is_print_dbginfo:
			print("WatchdogThread.run() from a thread.")

		self.feed_dog()

		while True:

			with self._mutex:
				now_tick = now_tick_monotonic()
				wait_secs = 0 # set later

				chk = (self._is_once_timeout, self._is_final_deadline)
				if chk==(True, True):
					wait_secs = min(self._moving_deadline, self._final_deadline) - now_tick
				elif chk==(True, False):
					wait_secs = self._moving_deadline - now_tick
				elif chk==(False, True):
					wait_secs = self._final_deadline - now_tick
				else: # (False, False)
					wait_secs = None # will wait infinitely

			if wait_secs!=None:
				if wait_secs<=0: # the main-thread has timed-out

					if self._is_print_dbginfo:
						print("WatchdogThread._timeout_action() calling...")

					ret = self._timeout_action(*self._action_args)
					return ret

			# Now we wait.
			is_work_done = self._evt_done.wait(wait_secs)
			if is_work_done:
				return None

			# Go back to start of while-cycle to check whether we have further seconds to wait.

		assert(0) # will not get here


@contextmanager
def pipe_process_with_timeout(subproc, once_timeout_sec, max_run_seconds, is_print_dbginfo=False):
	"""This context manager put the subproc operation under the monitoring of a auto-created watchdog thread.
	If the context code(code in the with...block) fails to feed the dog every once_timeout_sec,
	or max_run_seconds elapsed, subproc.kill() will be issued by the thread.

	This is useful when you want to call the potentially forever-blocking subproc.stdout.readline(),
	because the .kill() by the watchdog thread will render blocking pipe read to return.

	To feed the dog, write code like below:

	subproc = subprocess.Popen(...)
	with pipe_process_with_timeout(subproc, ...) as watchdog:
		for linebytes in subproc.stdout:
			if not linebytes:
				break
			# do something with linebytes...
			watchdog.feed_dog()

	:param subproc:
		The Popen object returned from subprocess.Popen() .

	:param once_timeout_sec:
		If feed_dog() has not been called these many seconds, the subproc will be killed by the watchdog thread.

	:param max_run_seconds:
		If the subproc has run for these many seconds, it will be killed.

	:return: An implicit context-manager object.
	"""

	thread_name = 'WatchdogThread for pid=%d. (timeout=%d,%d)'%(subproc.pid, once_timeout_sec, max_run_seconds)
	dogthread = WatchdogThread(once_timeout_sec, max_run_seconds, subproc.kill,
							is_print_dbginfo=is_print_dbginfo,
	                        name=thread_name)
	dogthread.start()

	try:
		yield dogthread
	finally:
		dogthread.work_done()


if __name__=='__main__':
	"""
python3 -m cheese.subprocess_tools.watchdog 2,30 "./sleep-print 1000 1900 3000 4000"
python3 -m cheese.subprocess_tools.watchdog 2,4 "./sleep-print 990 990 990 990 990"
	"""

	once_secs, total_secs = [int(n) for n in sys.argv[1].split(',')]
	sleep_print_cmd = sys.argv[2]
	print("Will run %d,%d seconds"%(once_secs, total_secs))
#	uesec_limit = uesec_now() + run_seconds

	with subprocess.Popen(sleep_print_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as subproc:

		with pipe_process_with_timeout(subproc, once_secs, total_secs, is_print_dbginfo=True) as watchdog:
			for linebytes in subproc.stdout:
				if not linebytes:
					break
				print("###%s"%(linebytes.decode('utf8')), end='')
				watchdog.feed_dog()

#	run_exe_log_output_and_print(sleep_print_cmd.split(), uesec_limit)
	pass
