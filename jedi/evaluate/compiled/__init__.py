"""
Imitate the parser representation.
"""
import inspect
import re
import sys
import os
from functools import partial

from jedi._compatibility import builtins as _builtins, unicode
from jedi import debug
from jedi.cache import underscore_memoization, memoize_method
from jedi.parser.tree import Param, Base, Operator, zero_position_modifier
from jedi.evaluate.helpers import FakeName
from . import fake


_sep = os.path.sep
if os.path.altsep is not None:
    _sep += os.path.altsep
_path_re = re.compile('(?:\.[^{0}]+|[{0}]__init__\.py)$'.format(re.escape(_sep)))
del _sep


class CheckAttribute(object):
    """Raises an AttributeError if the attribute X isn't available."""
    def __init__(self, func):
        self.func = func
        # Remove the py in front of e.g. py__call__.
        self.check_name = func.__name__[2:]

    def __get__(self, instance, owner):
        # This might raise an AttributeError. That's wanted.
        getattr(instance.obj, self.check_name)
        return partial(self.func, instance)


class CompiledObject(Base):
    # comply with the parser
    start_pos = 0, 0
    path = None  # modules have this attribute - set it to None.
    used_names = {}  # To be consistent with modules.

    def __init__(self, evaluator, obj, parent=None):
        self._evaluator = evaluator
        self.obj = obj
        self.parent = parent

    @CheckAttribute
    def py__call__(self, params):
        if inspect.isclass(self.obj):
            from jedi.evaluate.representation import Instance
            return set([Instance(self._evaluator, self, params)])
        else:
            return set(self._execute_function(params))

    @CheckAttribute
    def py__class__(self):
        return create(self._evaluator, self.obj.__class__, parent=self.parent)

    @CheckAttribute
    def py__mro__(self):
        return tuple(create(self._evaluator, cls, self.parent) for cls in self.obj.__mro__)

    @CheckAttribute
    def py__bases__(self):
        return tuple(create(self._evaluator, cls) for cls in self.obj.__bases__)

    def py__bool__(self):
        return bool(self.obj)

    def py__file__(self):
        return self.obj.__file__

    def is_class(self):
        return inspect.isclass(self.obj)

    @property
    def doc(self):
        return inspect.getdoc(self.obj) or ''

    @property
    def params(self):
        params_str, ret = self._parse_function_doc()
        tokens = params_str.split(',')
        if inspect.ismethoddescriptor(self._cls().obj):
            tokens.insert(0, 'self')
        params = []
        for p in tokens:
            parts = [FakeName(part) for part in p.strip().split('=')]
            if len(parts) > 1:
                parts.insert(1, Operator(zero_position_modifier, '=', (0, 0)))
            params.append(Param(parts, self))
        return params

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, repr(self.obj))

    @underscore_memoization
    def _parse_function_doc(self):
        if self.doc is None:
            return '', ''

        return _parse_function_doc(self.doc)

    def api_type(self):
        if fake.is_class_instance(self.obj):
            return 'instance'

        cls = self._cls().obj
        if inspect.isclass(cls):
            return 'class'
        elif inspect.ismodule(cls):
            return 'module'
        elif inspect.isbuiltin(cls) or inspect.ismethod(cls) \
                or inspect.ismethoddescriptor(cls):
            return 'function'

    @property
    def type(self):
        """Imitate the tree.Node.type values."""
        cls = self._cls().obj
        if inspect.isclass(cls):
            return 'classdef'
        elif inspect.ismodule(cls):
            return 'file_input'
        elif inspect.isbuiltin(cls) or inspect.ismethod(cls) \
                or inspect.ismethoddescriptor(cls):
            return 'funcdef'

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
            return create(self._evaluator, c, self.parent)
        return self

    @property
    def names_dict(self):
        # For compatibility with `representation.Class`.
        return self.names_dicts(False)[0]

    def names_dicts(self, search_global, is_instance=False):
        return self._names_dict_ensure_one_dict(is_instance)

    @memoize_method
    def _names_dict_ensure_one_dict(self, is_instance):
        """
        search_global shouldn't change the fact that there's one dict, this way
        there's only one `object`.
        """
        return [LazyNamesDict(self._evaluator, self._cls(), is_instance)]

    def get_subscope_by_name(self, name):
        if name in dir(self._cls().obj):
            return CompiledName(self._evaluator, self._cls(), name).parent
        else:
            raise KeyError("CompiledObject doesn't have an attribute '%s'." % name)

    @CheckAttribute
    def py__getitem__(self, index):
        if type(self.obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return set()

        return set([create(self._evaluator, self.obj[index])])

    @CheckAttribute
    def py__iter__(self):
        if type(self.obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return

        for part in self.obj:
            yield set([create(self._evaluator, part)])

    @property
    def name(self):
        # might not exist sometimes (raises AttributeError)
        return FakeName(self._cls().obj.__name__, self)

    def _execute_function(self, params):
        if self.type != 'funcdef':
            return

        for name in self._parse_function_doc()[1].split():
            try:
                bltn_obj = getattr(_builtins, name)
            except AttributeError:
                continue
            else:
                if bltn_obj is None:
                    # We want to evaluate everything except None.
                    # TODO do we?
                    continue
                bltn_obj = create(self._evaluator, bltn_obj)
                for result in self._evaluator.execute(bltn_obj, params):
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


class LazyNamesDict(object):
    """
    A names_dict instance for compiled objects, resembles the parser.tree.
    """
    def __init__(self, evaluator, compiled_obj, is_instance):
        self._evaluator = evaluator
        self._compiled_obj = compiled_obj
        self._is_instance = is_instance

    def __iter__(self):
        return (v[0].value for v in self.values())

    @memoize_method
    def __getitem__(self, name):
        try:
            getattr(self._compiled_obj.obj, name)
        except AttributeError:
            raise KeyError('%s in %s not found.' % (name, self._compiled_obj))
        return [CompiledName(self._evaluator, self._compiled_obj, name)]

    def values(self):
        obj = self._compiled_obj.obj

        values = []
        for name in dir(obj):
            try:
                values.append(self[name])
            except KeyError:
                # The dir function can be wrong.
                pass

        # dir doesn't include the type names.
        if not inspect.ismodule(obj) and obj != type and not self._is_instance:
            values += create(self._evaluator, type).names_dict.values()
        return values


class CompiledName(FakeName):
    def __init__(self, evaluator, obj, name):
        super(CompiledName, self).__init__(name)
        self._evaluator = evaluator
        self._obj = obj
        self.name = name

    def __repr__(self):
        try:
            name = self._obj.name  # __name__ is not defined all the time
        except AttributeError:
            name = None
        return '<%s: (%s).%s>' % (type(self).__name__, name, self.name)

    def is_definition(self):
        return True

    @property
    @underscore_memoization
    def parent(self):
        module = self._obj.get_parent_until()
        return _create_from_name(self._evaluator, module, self._obj, self.name)

    @parent.setter
    def parent(self, value):
        pass  # Just ignore this, FakeName tries to overwrite the parent attribute.


def dotted_from_fs_path(fs_path, sys_path):
    """
    Changes `/usr/lib/python3.4/email/utils.py` to `email.utils`.  I.e.
    compares the path with sys.path and then returns the dotted_path. If the
    path is not in the sys.path, just returns None.
    """
    if os.path.basename(fs_path).startswith('__init__.'):
        # We are calculating the path. __init__ files are not interesting.
        fs_path = os.path.dirname(fs_path)

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
        if (fs_path.startswith(s) and len(path) < len(s)):
            path = s
    return _path_re.sub('', fs_path[len(path):].lstrip(os.path.sep)).replace(os.path.sep, '.')


def load_module(evaluator, path=None, name=None):
    sys_path = evaluator.sys_path
    if path is not None:
        dotted_path = dotted_from_fs_path(path, sys_path=sys_path)
    else:
        dotted_path = name

    if dotted_path is None:
        p, _, dotted_path = path.partition(os.path.sep)
        sys_path.insert(0, p)

    temp, sys.path = sys.path, sys_path
    try:
        __import__(dotted_path)
    except RuntimeError:
        if 'PySide' in dotted_path or 'PyQt' in dotted_path:
            # RuntimeError: the PyQt4.QtCore and PyQt5.QtCore modules both wrap
            # the QObject class.
            # See https://github.com/davidhalter/jedi/pull/483
            return None
        raise
    except ImportError:
        # If a module is "corrupt" or not really a Python module or whatever.
        debug.warning('Module %s not importable.', path)
        return None
    finally:
        sys.path = temp

    # Just access the cache after import, because of #59 as well as the very
    # complicated import structure of Python.
    module = sys.modules[dotted_path]

    return create(evaluator, module)


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


def _create_from_name(evaluator, module, parent, name):
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
    return create(evaluator, obj, parent)


def builtin_from_name(evaluator, string):
    bltn_obj = getattr(_builtins, string)
    return create(evaluator, bltn_obj)


def _a_generator(foo):
    """Used to have an object to return for generators."""
    yield 42
    yield foo


_SPECIAL_OBJECTS = {
    'FUNCTION_CLASS': type(load_module),
    'MODULE_CLASS': type(os),
    'GENERATOR_OBJECT': _a_generator(1.0),
    'BUILTINS': _builtins,
}


def get_special_object(evaluator, identifier):
    obj = _SPECIAL_OBJECTS[identifier]
    return create(evaluator, obj, parent=create(evaluator, _builtins))


def compiled_objects_cache(func):
    def wrapper(evaluator, obj, parent=None, module=None):
        # Do a very cheap form of caching here.
        key = id(obj)
        try:
            return evaluator.compiled_cache[key][0]
        except KeyError:
            result = func(evaluator, obj, parent, module)
            # Need to cache all of them, otherwise the id could be overwritten.
            evaluator.compiled_cache[key] = result, obj, parent, module
            return result
    return wrapper


@compiled_objects_cache
def create(evaluator, obj, parent=None, module=None):
    """
    A very weird interface class to this module. The more options provided the
    more acurate loading compiled objects is.
    """
    if parent is None and not inspect.ismodule(obj):
        parent = create(evaluator, _builtins)

    if not inspect.ismodule(obj):
        faked = fake.get_faked(module and module.obj, obj)
        if faked is not None:
            faked.parent = parent
            return faked

    return CompiledObject(evaluator, obj, parent)
