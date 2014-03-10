""" Mostly for stupid error reports of @dbrgn. :-) """

import time

class Foo(object):
    global time
    asdf = time

def asdfy():
    return Foo

xorz = getattr(asdfy()(), 'asdf')
#? time
xorz
