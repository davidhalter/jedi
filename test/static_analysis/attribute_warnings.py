"""
Jedi issues warnings for possible errors if ``__getattr__``,
``__getattribute__`` or ``setattr`` are used.
"""


class Cls():
    def __getattr__(self, name):
        return getattr(str, name)


Cls().upper

#! 6 warning attribute-error
Cls().undefined


class Inherited(Cls):
    pass

Inherited().upper

#! 12 warning attribute-error
Inherited().undefined
