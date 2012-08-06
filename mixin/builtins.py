"""
Pure Python implementation of some builtins.
This code is not going to be executed anywhere.
These implementations are not always correct, but should work as good as
possible for the auto completion.
"""


def next(iterator, default=None):
    if hasattr("next"):
        return iterator.next()
    else:
        return iterator.__next__()
    return default


def iter(collection, sentinel=None):
    if sentinel:
        yield collection()
    else:
        yield next(collection)


#--------------------------------------------------------
# descriptors
#--------------------------------------------------------
class property():
    def __init__(self, fget, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc

    def __get__(self, obj, cls):
        return self.fget(obj)

    def __set__(self, obj, value):
        self.fset(obj, value)

    def __delete__(self, obj):
        self.fdel(obj)

    def setter(self, func):
        self.fset = func
        return self

    def getter(self, func):
        self.fget = func
        return self

    def deleter(self, func):
        self.fdel = func
        return self


class staticmethod():
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        return self.func


class classmethod():
    def __init__(self, func):
        self._func = func

    def __get__(self, obj, cls):
        def _method(*args, **kwargs):
            return self._func(cls, *args, **kwargs)
        return _method


#--------------------------------------------------------
# array stuff
#--------------------------------------------------------
class list():
    def __init__(self, iterable=[]):
        self.iterable = []
        for i in iterable:
            self.iterable += [i]

    def __iter__(self):
        for i in self.iterable:
            yield i

    def __getitem__(self, y):
        return self.iterable[y]

    def pop(self):
        return self.iterable[-1]


class set():
    def __init__(self, iterable=[]):
        self.iterable = iterable

    def __iter__(self):
        for i in self.iterable:
            yield i

    def add(self, elem):
        self.iterable += [elem]

    def pop(self):
        return self.iterable.pop()

    def copy(self):
        return self


#--------------------------------------------------------
# basic types
#--------------------------------------------------------
class int():
    def __init__(self, x, base=None):
        self.x = x


class str():
    def __init__(self, obj):
        self.obj = obj
