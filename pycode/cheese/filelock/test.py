#!/usr/bin/env python3
# coding: utf-8

from .assistive_filelock import *

if __name__=='__main__':
    filelock = AsFilelock ("t1.lck")

    try:
        filelock.lock()
        print('Lock success.')
    except Err_asfilelock as e:
        print(e.errmsg)
        exit(4)

    print('Now unlock.')
    filelock.unlock()

