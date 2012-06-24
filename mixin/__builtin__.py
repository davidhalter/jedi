
def next(iterator, default=None):
    if hasattr("next"):
        return iterator.next()
    else:
        return iterator.__next__()
    return default

class property():
    def __init__(self, fget, fset = None, fdel = None, doc = None):
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
            self._func(cls, *args, **kwargs)
        return _method
