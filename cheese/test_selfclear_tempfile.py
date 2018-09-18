import sys
import time
#import selfclear_tempfile

from selfclear_tempfile import (fakefs, SelfclearTempfile)

import pytest

Prefix = 'kiss-'
Suffix = '.tmp'

def test_simple1():
	sctf = SelfclearTempfile('.', Prefix, Suffix)
	
	fh = sctf.create_new()
	print("[[[Created filepath is: %s]]]"%fh.name)
#	time.sleep(3)
	fh.close()


def test_fakefs1():
	
	def assert_file_count(n):
		assert n == len(scobj.listfiles())
	
	scobj = SelfclearTempfile(".", Prefix, Suffix, 
			preserve_seconds=3600, 
			scan_delay_seconds=60,
			filesys=fakefs.FakeFs()
			)
	
	fn_sec0 = scobj.create_new(0) # Create first file at Unix Epoch
#	print(">>>>>>>>>>>" , scobj.listfiles())
	assert_file_count(2) # one is tmp file, the other is .cleancheck
#	print("_scandir_count=", scobj._scandir_count)
	assert 1==scobj._scandir_count

	assert fn_sec0 in scobj.listfiles()

	scobj.create_new(1.0) # Create one more file at Unix Epoch+1 second
	assert_file_count(3)
	assert 1==scobj._scandir_count

	scobj.create_new(2.0) # Create one more file at Unix Epoch+1 second
	assert_file_count(4)
	assert 1==scobj._scandir_count

	scobj.create_new(60.0)
	assert_file_count(5)
	assert 2==scobj._scandir_count
	
	scobj.create_new(61.0)
	assert_file_count(6)
	assert 2==scobj._scandir_count
	
	assert fn_sec0 in scobj.listfiles()

	# An action on sec:3600, fn_sec0 will be cleared
	scobj.create_new(3600.0)
	assert_file_count(6) # new one, delete one, so still 6
	assert 3==scobj._scandir_count
	assert not fn_sec0 in scobj.listfiles()


if __name__=='__main__':
#	test_simple1()
	test_fakefs1()
