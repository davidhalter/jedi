"""
To ensure compatibility from Python ``2.6`` - ``3.3``, a module has been
created. Clearly there is huge need to use conforming syntax. But many changes
(e.g. ``property``, ``hasattr`` in ``2.5``) can be rewritten in pure python.
"""
import sys
import imp
import os
try:
    import importlib
except ImportError:
    pass

is_py3k = sys.hexversion >= 0x03000000
is_py33 = sys.hexversion >= 0x03030000


def find_module_py33(string, path=None):
    loader = importlib.machinery.PathFinder.find_module(string, path)

    if loader is None and path is None:  # Fallback to find builtins
        loader = importlib.find_loader(string)

    if loader is None:
        raise ImportError("Couldn't find a loader for {0}".format(string))

    try:
        is_package = loader.is_package(string)
        if is_package:
            module_path = os.path.dirname(loader.path)
            module_file = None
        else:
            module_path = loader.get_filename(string)
            module_file = open(module_path)
    except AttributeError:
        # is builtin module
        module_path = string
        module_file = None
        is_package = False

    return module_file, module_path, is_package


def find_module_pre_py33(string, path=None):
    module_file, module_path, description = imp.find_module(string, path)
    module_type = description[2]
    return module_file, module_path, module_type is imp.PKG_DIRECTORY


find_module = find_module_py33 if is_py33 else find_module_pre_py33
find_module.__doc__ = """
Provides information about a module.

This function isolates the differences in importing libraries introduced with
python 3.3 on; it gets a module name and optionally a path. It will return a
tuple containin an open file for the module (if not builtin), the filename
or the name of the module if it is a builtin one and a boolean indicating
if the module is contained in a package.
"""

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

def use_metaclass(meta, *bases):
    """ Create a class with a metaclass. """
    if not bases:
        bases = (object,)
    return meta("HackClass", bases, {})

try:
    from functools import reduce  # Python 3
except ImportError:
    reduce = reduce

try:
    encoding = sys.stdout.encoding
    if encoding is None:
        encoding = 'utf-8'
except AttributeError:
    encoding = 'ascii'

def u(string):
    """Cast to unicode DAMMIT!
    Written because Python2 repr always implicitly casts to a string, so we
    have to cast back to a unicode (and we now that we always deal with valid
    unicode, because we check that in the beginning).
    """
    if is_py3k:
        return str(string)
    elif not isinstance(string, unicode):
        return unicode(str(string), 'UTF-8')
    return string

try:
    import builtins  # module name in python 3
except ImportError:
    import __builtin__ as builtins
