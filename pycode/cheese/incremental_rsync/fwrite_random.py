#!/usr/bin/env python3
# coding: utf-8

import os, sys
import random

def fwrite_random(filepath, offset, len):
	"""Write random content to filepath, at offset, len bytes."""

	fh = None
	if os.path.isfile(filepath):
		fh = open(filepath, "rb+")
	else:
		fh = open(filepath, "wb")

	buf = bytearray(len)
	for i in range(len):
		buf[i] = random.randint(0, 255)

	fh.seek(offset, os.SEEK_SET)
	fh.write(buf)
	fh.close()

if __name__=='__main__':
	if len(sys.argv)==1:
		print("Usage: fwrite_random <file> <offset> <len>")
		exit(4)
	fwrite_random(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
