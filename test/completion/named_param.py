""" named params:
>>> def a(abc): pass
>>> a(abc=3)  # <- this stuff
"""

def a(abc):
    pass

#? 5 ['abc']
a(abc)
