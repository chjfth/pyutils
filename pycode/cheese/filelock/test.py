#!/usr/bin/env python3
# coding: utf-8

from .assistive_filelock import *

if __name__=='__main__':
    filelock = AsFilelock ("t1.lck")
    filelock.lock()
    filelock.unlock()

