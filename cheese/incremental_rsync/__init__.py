
#__all__ = ["share", "client"]

from .share import *

print("aaa")
from .client import *
print("bbb")

Err_irsync = share.Err_irsync

#zz = rsync_fetch_once
