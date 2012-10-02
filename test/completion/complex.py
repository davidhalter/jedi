""" Mainly for stupid error reports of @gwrtheyrn. :-) """

import time

class Foo(object):
    global time
    asdf = time

def asdfy():
    return Foo

xorz = getattr(asdfy()(), 'asdf')
#? time
xorz
