"""
Named Params:
>>> def a(abc): pass
...
>>> a(abc=3)  # <- this stuff (abc)
"""

def a(abc):
    pass

#? 5 ['abc']
a(abc)


def a(*some_args, **some_kwargs):
    pass

#? 11 []
a(some_args)

#? 13 []
a(some_kwargs)

def multiple(foo, bar):
    pass

#? 17 ['bar']
multiple(foo, bar)

#? ['bar']
multiple(foo, bar
