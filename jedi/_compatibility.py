"""
To ensure compatibility from Python ``2.5`` - ``3.2``, a module has been
created. Clearly there is huge need to use conforming syntax. But many changes
(e.g. ``property``, ``hasattr`` in ``2.5``) can be rewritten in pure python.

Most of the code here is necessary to support Python 2.5. Once this dependency
will be dropped, we'll get rid of most code.
"""
import sys
import imp
import os
try:
    import importlib
except:
    pass

is_py3k = sys.hexversion >= 0x03000000
is_py33 = sys.hexversion >= 0x03030000
is_py25 = sys.hexversion < 0x02060000

def find_module_py33(string, path=None):
    mod_info = (None, None, None)
    loader = None
    if path is not None:
        # Check for the module in the specidied path
        loader = importlib.machinery.PathFinder.find_module(string, path)
    else:
        # Check for the module in sys.path
        loader = importlib.machinery.PathFinder.find_module(string, sys.path)
        if loader is None:
            # Fallback to find builtins
            loader = importlib.find_loader(string)

    if loader is None:
        raise ImportError

    try:
        if (loader.is_package(string)):
            mod_info = (None, os.path.dirname(loader.path), True)
        else:
            filename = loader.get_filename(string)
            if filename and os.path.exists(filename):
                mod_info = (open(filename, 'U'), filename, False)
            else:
                mod_info = (None, filename, False)
    except AttributeError:
        mod_info = (None, loader.load_module(string).__name__, False)

    return mod_info

def find_module_pre_py33(string, path=None):
    mod_info = None
    if path is None:
        mod_info = imp.find_module(string)
    else:
        mod_info = imp.find_module(string, path)

    return (mod_info[0], mod_info[1], mod_info[2][2] == imp.PKG_DIRECTORY)

def find_module(string, path=None):
    """Provides information about a module.

    This function isolates the differences in importing libraries introduced with
    python 3.3 on; it gets a module name and optionally a path. It will return a
    tuple containin an open file for the module (if not builtin), the filename
    or the name of the module if it is a builtin one and a boolean indicating
    if the module is contained in a package."""
    if is_py33:
        return find_module_py33(string, path)
    else:
        return find_module_pre_py33(string, path)

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
    unicode = str

if is_py3k:
    utf8 = lambda s: s
else:
    utf8 = lambda s: s.decode('utf-8')

utf8.__doc__ = """
Decode a raw string into unicode object.  Do nothing in Python 3.
"""

# exec function
if is_py3k:
    def exec_function(source, global_map):
        exec(source, global_map)
else:
    eval(compile("""def exec_function(source, global_map):
                        exec source in global_map """, 'blub', 'exec'))

# re-raise function
if is_py3k:
    def reraise(exception, traceback):
        raise exception.with_traceback(traceback)
else:
    eval(compile("""
def reraise(exception, traceback):
    raise exception, None, traceback
""", 'blub', 'exec'))

reraise.__doc__ = """
Re-raise `exception` with a `traceback` object.

Usage::

    reraise(Exception, sys.exc_info()[2])

"""

# StringIO (Python 2.5 has no io module), so use io only for py3k
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

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

try:
    from functools import reduce
except ImportError:
    reduce = reduce

try:
    import json
except ImportError:
    # python 2.5
    import simplejson as json

try:
    encoding = sys.stdout.encoding
except AttributeError:
    encoding = 'ascii'
