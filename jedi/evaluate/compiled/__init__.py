"""
Imitate the parser representation.
"""
import inspect
import re
import sys
import os

from jedi._compatibility import builtins as _builtins, unicode
from jedi import debug
from jedi.cache import underscore_memoization, memoize
from jedi.evaluate.sys_path import get_sys_path
from jedi.parser.representation import Param, SubModule, Base, IsScope, Operator
from jedi.evaluate.helpers import FakeName
from . import fake


_sep = os.path.sep
if os.path.altsep is not None:
    _sep += os.path.altsep
_path_re = re.compile('(?:\.[^{0}]+|[{0}]__init__\.py)$'.format(re.escape(_sep)))
del _sep


class CompiledObject(Base):
    # comply with the parser
    start_pos = 0, 0
    asserts = []
    path = None  # modules have this attribute - set it to None.

    def __init__(self, obj, parent=None):
        self.obj = obj
        self.parent = parent

    @property
    def doc(self):
        return inspect.getdoc(self.obj) or ''

    @property
    def params(self):
        params_str, ret = self._parse_function_doc()
        tokens = params_str.split(',')
        params = []
        module = SubModule(self.get_parent_until().name)
        # it seems like start_pos/end_pos is always (0, 0) for a compiled
        # object
        start_pos, end_pos = (0, 0), (0, 0)
        for p in tokens:
            parts = [FakeName(part) for part in p.strip().split('=')]
            if len(parts) >= 2:
                parts.insert(1, Operator(module, '=', module, (0, 0)))
            params.append(Param(module, parts, start_pos,
                                end_pos, builtin))
        return params

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, repr(self.obj))

    @underscore_memoization
    def _parse_function_doc(self):
        if self.doc is None:
            return '', ''

        return _parse_function_doc(self.doc)

    def type(self):
        cls = self._cls().obj
        if inspect.isclass(cls):
            return 'class'
        elif inspect.ismodule(cls):
            return 'module'
        elif inspect.isbuiltin(cls) or inspect.ismethod(cls) \
                or inspect.ismethoddescriptor(cls):
            return 'function'

    def is_executable_class(self):
        return inspect.isclass(self.obj)

    @underscore_memoization
    def _cls(self):
        # Ensures that a CompiledObject is returned that is not an instance (like list)
        if fake.is_class_instance(self.obj):
            try:
                c = self.obj.__class__
            except AttributeError:
                # happens with numpy.core.umath._UFUNC_API (you get it
                # automatically by doing `import numpy`.
                c = type(None)
            return CompiledObject(c, self.parent)
        return self

    def get_defined_names(self):
        if inspect.ismodule(self.obj):
            return self.instance_names()
        else:
            return type_names + self.instance_names()

    def scope_names_generator(self, position=None):
        yield self, self.get_defined_names()

    @underscore_memoization
    def instance_names(self):
        names = []
        cls = self._cls()
        for name in dir(cls.obj):
            names.append(CompiledName(cls, name))
        return names

    def get_subscope_by_name(self, name):
        if name in dir(self._cls().obj):
            return CompiledName(self._cls(), name).parent
        else:
            raise KeyError("CompiledObject doesn't have an attribute '%s'." % name)

    def get_index_types(self, evaluator, index_array):
        # If the object doesn't have `__getitem__`, just raise the
        # AttributeError.
        if not hasattr(self.obj, '__getitem__'):
            debug.warning('Tried to call __getitem__ on non-iterable.')
            return []
        if type(self.obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return []

        result = []
        from jedi.evaluate.iterable import create_indexes_or_slices
        for typ in create_indexes_or_slices(evaluator, index_array):
            index = None
            try:
                index = typ.obj
                new = self.obj[index]
            except (KeyError, IndexError, TypeError, AttributeError):
                # Just try, we don't care if it fails, except for slices.
                if isinstance(index, slice):
                    result.append(self)
            else:
                result.append(CompiledObject(new))
        if not result:
            try:
                for obj in self.obj:
                    result.append(CompiledObject(obj))
            except TypeError:
                pass  # self.obj maynot have an __iter__ method.
        return result

    @property
    def name(self):
        # might not exist sometimes (raises AttributeError)
        return self._cls().obj.__name__

    def execute_function(self, evaluator, params):
        if self.type() != 'function':
            return

        for name in self._parse_function_doc()[1].split():
            try:
                bltn_obj = _create_from_name(builtin, builtin, name)
            except AttributeError:
                continue
            else:
                if isinstance(bltn_obj, CompiledObject):
                    # We want everything except None.
                    if bltn_obj.obj is not None:
                        yield bltn_obj
                else:
                    for result in evaluator.execute(bltn_obj, params):
                        yield result

    @property
    @underscore_memoization
    def subscopes(self):
        """
        Returns only the faked scopes - the other ones are not important for
        internal analysis.
        """
        module = self.get_parent_until()
        faked_subscopes = []
        for name in dir(self._cls().obj):
            f = fake.get_faked(module.obj, self.obj, name)
            if f:
                f.parent = self
                faked_subscopes.append(f)
        return faked_subscopes

    def is_scope(self):
        return True

    def get_self_attributes(self):
        return []  # Instance compatibility

    def get_imports(self):
        return []  # Builtins don't have imports

    def is_callable(self):
        """Check if the object has a ``__call__`` method."""
        return hasattr(self.obj, '__call__')


class CompiledName(FakeName):
    def __init__(self, obj, name):
        super(CompiledName, self).__init__(name)
        self._obj = obj
        self.name = name
        self.start_pos = 0, 0  # an illegal start_pos, to make sorting easy.

    def __repr__(self):
        try:
            name = self._obj.name  # __name__ is not defined all the time
        except AttributeError:
            name = None
        return '<%s: (%s).%s>' % (type(self).__name__, name, self.name)

    @property
    @underscore_memoization
    def parent(self):
        module = self._obj.get_parent_until()
        return _create_from_name(module, self._obj, self.name)

    @parent.setter
    def parent(self, value):
        pass  # Just ignore this, FakeName tries to overwrite the parent attribute.


def dotted_from_fs_path(fs_path, sys_path=None):
    """
    Changes `/usr/lib/python3.4/email/utils.py` to `email.utils`.  I.e.
    compares the path with sys.path and then returns the dotted_path. If the
    path is not in the sys.path, just returns None.
    """
    if sys_path is None:
        sys_path = get_sys_path()

    # prefer
    #   - UNIX
    #     /path/to/pythonX.Y/lib-dynload
    #     /path/to/pythonX.Y/site-packages
    #   - Windows
    #     C:\path\to\DLLs
    #     C:\path\to\Lib\site-packages
    # over
    #   - UNIX
    #     /path/to/pythonX.Y
    #   - Windows
    #     C:\path\to\Lib
    path = ''
    for s in sys_path:
        if (fs_path.startswith(s) and
            len(path) < len(s)):
            path = s
    return _path_re.sub('', fs_path[len(path):].lstrip(os.path.sep)).replace(os.path.sep, '.')


def load_module(path, name):
    """
    if not name:
        name = os.path.basename(path)
        name = name.rpartition('.')[0]  # cut file type (normally .so)

    # sometimes there are endings like `_sqlite3.cpython-32mu`
    name = re.sub(r'\..*', '', name)

    dot_path = []
    if path:
        p = path
        # if path is not in sys.path, we need to make a well defined import
        # like `from numpy.core import umath.`
        while p and p not in sys.path:
            p, sep, mod = p.rpartition(os.path.sep)
            dot_path.insert(0, mod.partition('.')[0])
        if p:
            name = ".".join(dot_path)
            path = p
        else:
            path = os.path.dirname(path)

    """
    if path is not None:
        dotted_path = dotted_from_fs_path(path)
    else:
        dotted_path = name

    sys_path = get_sys_path()
    if dotted_path is None:
        p, _, dotted_path = path.partition(os.path.sep)
        sys_path.insert(0, p)

    temp, sys.path = sys.path, sys_path
    __import__(dotted_path)
    # Just access the cache after import, because of #59 as well as the very
    # complicated import structure of Python.
    module = sys.modules[dotted_path]
    sys.path = temp
    return CompiledObject(module)


docstr_defaults = {
    'floating point number': 'float',
    'character': 'str',
    'integer': 'int',
    'dictionary': 'dict',
    'string': 'str',
}


def _parse_function_doc(doc):
    """
    Takes a function and returns the params and return value as a tuple.
    This is nothing more than a docstring parser.

    TODO docstrings like utime(path, (atime, mtime)) and a(b [, b]) -> None
    TODO docstrings like 'tuple of integers'
    """
    # parse round parentheses: def func(a, (b,c))
    try:
        count = 0
        start = doc.index('(')
        for i, s in enumerate(doc[start:]):
            if s == '(':
                count += 1
            elif s == ')':
                count -= 1
            if count == 0:
                end = start + i
                break
        param_str = doc[start + 1:end]
    except (ValueError, UnboundLocalError):
        # ValueError for doc.index
        # UnboundLocalError for undefined end in last line
        debug.dbg('no brackets found - no param')
        end = 0
        param_str = ''
    else:
        # remove square brackets, that show an optional param ( = None)
        def change_options(m):
            args = m.group(1).split(',')
            for i, a in enumerate(args):
                if a and '=' not in a:
                    args[i] += '=None'
            return ','.join(args)

        while True:
            param_str, changes = re.subn(r' ?\[([^\[\]]+)\]',
                                         change_options, param_str)
            if changes == 0:
                break
    param_str = param_str.replace('-', '_')  # see: isinstance.__doc__

    # parse return value
    r = re.search('-[>-]* ', doc[end:end + 7])
    if r is None:
        ret = ''
    else:
        index = end + r.end()
        # get result type, which can contain newlines
        pattern = re.compile(r'(,\n|[^\n-])+')
        ret_str = pattern.match(doc, index).group(0).strip()
        # New object -> object()
        ret_str = re.sub(r'[nN]ew (.*)', r'\1()', ret_str)

        ret = docstr_defaults.get(ret_str, ret_str)

    return param_str, ret


class Builtin(CompiledObject, IsScope):
    @memoize
    def get_by_name(self, name):
        item = [n for n in self.get_defined_names() if n.get_code() == name][0]
        return item.parent


def _a_generator(foo):
    """Used to have an object to return for generators."""
    yield 42
    yield foo


def _create_from_name(module, parent, name):
    faked = fake.get_faked(module.obj, parent.obj, name)
    # only functions are necessary.
    if faked is not None:
        faked.parent = parent
        return faked

    try:
        obj = getattr(parent.obj, name)
    except AttributeError:
        # happens e.g. in properties of
        # PyQt4.QtGui.QStyleOptionComboBox.currentText
        # -> just set it to None
        obj = None
    return CompiledObject(obj, parent)


builtin = Builtin(_builtins)
magic_function_class = CompiledObject(type(load_module), parent=builtin)
generator_obj = CompiledObject(_a_generator(1.0))
type_names = []  # Need this, because it's return in get_defined_names.
type_names = builtin.get_by_name('type').get_defined_names()


def compiled_objects_cache(func):
    def wrapper(evaluator, obj, parent=builtin, module=None):
        # Do a very cheap form of caching here.
        key = id(obj), id(parent), id(module)
        try:
            return evaluator.compiled_cache[key][0]
        except KeyError:
            result = func(evaluator, obj, parent, module)
            # Need to cache all of them, otherwise the id could be overwritten.
            evaluator.compiled_cache[key] = result, obj, parent, module
            return result
    return wrapper


@compiled_objects_cache
def create(evaluator, obj, parent=builtin, module=None):
    """
    A very weird interface class to this module. The more options provided the
    more acurate loading compiled objects is.
    """

    if not inspect.ismodule(obj):
        faked = fake.get_faked(module and module.obj, obj)
        if faked is not None:
            faked.parent = parent
            return faked

    return CompiledObject(obj, parent)
