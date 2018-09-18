import sys
import time
#import selfclear_tempfile

from selfclear_tempfile import (fakefs, SelfclearTempfile)

import pytest

Prefix = 'kiss-'
Suffix = '.tmp'

def test_simple1():
	sctf = SelfclearTempfile('.', Prefix, Suffix)
	
	fh = sctf.create_and_open(None)
	print("[[[Created filepath is: %s]]]"%fh.name) 
	time.sleep(3)
	fh.close()

if __name__=='__main__':
	test_simple1()
