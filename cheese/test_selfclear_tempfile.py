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
	
	scobj = SelfclearTempfile(".", Prefix, Suffix, 
			preserve_seconds=3600, 
			scan_delay_seconds=60,
			filesys=fakefs.FakeFs()
			)
	
	# Create first file at Unix Epoch
	fh = scobj.create_new(0)
	assert len(scobj.listfiles())==1


if __name__=='__main__':
#	test_simple1()
	test_fakefs1()
