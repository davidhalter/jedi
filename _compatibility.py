"""
This is a compatibility module, to make it possible to use jedi also with older
python versions.
"""
import sys

# next was defined in python 2.6, in python 3 obj.next won't be possible
# anymore
try:
    next = next
except NameError:
    _raiseStopIteration = object()

    def next(iterator, default=_raiseStopIteration):
        if not hasattr(iterator, 'next'):
            raise TypeError("not an iterator")
        try:
            return iterator.next()
        except StopIteration:
            if default is _raiseStopIteration:
                raise
            else:
                return default

# ast module was defined in python 2.6
try:
    from ast import literal_eval
except ImportError:
    literal_eval = eval


# properties in 2.5
try:
    property.setter
except AttributeError:
    class property(property):
        def __init__(self, fget, *args, **kwargs):
            self.__doc__ = fget.__doc__
            super(property, self).__init__(fget, *args, **kwargs)

        def setter(self, fset):
            cls_ns = sys._getframe(1).f_locals
            for k, v in cls_ns.iteritems():
                if v == self:
                    propname = k
                    break
            cls_ns[propname] = property(self.fget, fset,
                                        self.fdel, self.__doc__)
            return cls_ns[propname]
else:
    property = property

# unicode function
try:
    unicode = unicode
except NameError:
    def unicode(s):
        return s.decode("utf-8")

# exec function
if sys.hexversion >= 0x03000000:
    def exec_function(source, global_map):
        exec(source, global_map)
else:
    eval(compile("""def exec_function(source, global_map):
                        exec source in global_map """, 'blub', 'exec'))

# tokenize function
import tokenize
if sys.hexversion >= 0x03000000:
    tokenize_func = tokenize.tokenize
else:
    tokenize_func = tokenize.generate_tokens

# BytesIO (Python 2.5 has no io module)
try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO
