"""
This is a compatibility module, to make it possible to use jedi also with older
python versions.
"""
import sys

is_py3k = sys.hexversion >= 0x03000000

is_py25 = sys.hexversion < 0x02060000

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
if is_py3k:
    def exec_function(source, global_map):
        exec(source, global_map)
else:
    eval(compile("""def exec_function(source, global_map):
                        exec source in global_map """, 'blub', 'exec'))

# tokenize function
import tokenize
if is_py3k:
    tokenize_func = tokenize.tokenize
else:
    tokenize_func = tokenize.generate_tokens

# BytesIO (Python 2.5 has no io module)
try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

# hasattr function used because python
if is_py3k:
    hasattr = hasattr
else:
    def hasattr(obj, name):
        try:
            getattr(obj, name)
            return True
        except AttributeError:
            return False


class Python3Method(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype):
        if obj is None:
            return lambda *args, **kwargs: self.func(*args, **kwargs)
        else:
            return lambda *args, **kwargs: self.func(obj, *args, **kwargs)

try:
    # the python3 way
    from functools import reduce
except ImportError:
    reduce = reduce


def use_metaclass(meta, *bases):
    """ Create a class with a metaclass. """
    if not bases:
        bases = (object,)
    return meta("HackClass", bases, {})

try:
    from inspect import cleandoc
except ImportError:
    # python 2.5 doesn't have this method
    import string

    def cleandoc(doc):
        """Clean up indentation from docstrings.

        Any whitespace that can be uniformly removed from the second line
        onwards is removed."""
        try:
            lines = string.split(string.expandtabs(doc), '\n')
        except UnicodeError:
            return None
        else:
            # Find minimum indentation of any non-blank lines after first line.
            margin = sys.maxint
            for line in lines[1:]:
                content = len(string.lstrip(line))
                if content:
                    indent = len(line) - content
                    margin = min(margin, indent)
            # Remove indentation.
            if lines:
                lines[0] = lines[0].lstrip()
            if margin < sys.maxint:
                for i in range(1, len(lines)):
                    lines[i] = lines[i][margin:]
            # Remove any trailing or leading blank lines.
            while lines and not lines[-1]:
                lines.pop()
            while lines and not lines[0]:
                lines.pop(0)
            return string.join(lines, '\n')

if is_py25:
    # adds the `itertools.chain.from_iterable` constructor
    import itertools

    class chain(itertools.chain):
        @staticmethod
        def from_iterable(iterables):
            # chain.from_iterable(['ABC', 'DEF']) --> A B C D E F
            for it in iterables:
                for element in it:
                    yield element
    itertools.chain = chain
    del chain
