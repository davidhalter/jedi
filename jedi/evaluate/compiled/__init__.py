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
from jedi.parser.python.tree import Param, Operator
from jedi.evaluate.helpers import FakeName
from jedi.evaluate.filters import AbstractFilter, AbstractNameDefinition, \
    ContextNameMixin
from jedi.evaluate.context import Context, LazyKnownContext
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
        if self.check_name == '__iter__':
            # Python iterators are a bit strange, because there's no need for
            # the __iter__ function as long as __getitem__ is defined (it will
            # just start with __getitem__(0). This is especially true for
            # Python 2 strings, where `str.__iter__` is not even defined.
            try:
                iter(instance.obj)
            except TypeError:
                raise AttributeError
        else:
            getattr(instance.obj, self.check_name)
        return partial(self.func, instance)


class CompiledObject(Context):
    path = None  # modules have this attribute - set it to None.
    used_names = {}  # To be consistent with modules.

    def __init__(self, evaluator, obj, parent_context=None, faked_class=None):
        super(CompiledObject, self).__init__(evaluator, parent_context)
        self.obj = obj
        # This attribute will not be set for most classes, except for fakes.
        self.tree_node = faked_class

    def get_root_node(self):
        # To make things a bit easier with filters we add this method here.
        return self.get_root_context()

    @CheckAttribute
    def py__call__(self, params):
        if inspect.isclass(self.obj):
            from jedi.evaluate.instance import CompiledInstance
            return set([CompiledInstance(self.evaluator, self.parent_context, self, params)])
        else:
            return set(self._execute_function(params))

    @CheckAttribute
    def py__class__(self):
        return create(self.evaluator, self.obj.__class__)

    @CheckAttribute
    def py__mro__(self):
        return (self,) + tuple(create(self.evaluator, cls) for cls in self.obj.__mro__[1:])

    @CheckAttribute
    def py__bases__(self):
        return tuple(create(self.evaluator, cls) for cls in self.obj.__bases__)

    def py__bool__(self):
        return bool(self.obj)

    def py__file__(self):
        try:
            return self.obj.__file__
        except AttributeError:
            return None

    def is_class(self):
        return inspect.isclass(self.obj)

    @property
    def doc(self):
        return inspect.getdoc(self.obj) or ''

    @property
    def get_params(self):
        return []  # TODO Fix me.
        params_str, ret = self._parse_function_doc()
        tokens = params_str.split(',')
        if inspect.ismethoddescriptor(self.obj):
            tokens.insert(0, 'self')
        params = []
        for p in tokens:
            parts = [FakeName(part) for part in p.strip().split('=')]
            if len(parts) > 1:
                parts.insert(1, Operator('=', (0, 0)))
            params.append(Param(parts, self))
        return params

    def get_param_names(self):
        params_str, ret = self._parse_function_doc()
        tokens = params_str.split(',')
        if inspect.ismethoddescriptor(self.obj):
            tokens.insert(0, 'self')
        for p in tokens:
            parts = p.strip().split('=')
            if len(parts) > 1:
                parts.insert(1, Operator('=', (0, 0)))
            yield UnresolvableParamName(self, parts[0])

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, repr(self.obj))

    @underscore_memoization
    def _parse_function_doc(self):
        if self.doc is None:
            return '', ''

        return _parse_function_doc(self.doc)

    @property
    def api_type(self):
        obj = self.obj
        if inspect.isclass(obj):
            return 'class'
        elif inspect.ismodule(obj):
            return 'module'
        elif inspect.isbuiltin(obj) or inspect.ismethod(obj) \
                or inspect.ismethoddescriptor(obj) or inspect.isfunction(obj):
            return 'function'
        # Everything else...
        return 'instance'

    @property
    def type(self):
        """Imitate the tree.Node.type values."""
        cls = self._get_class()
        if inspect.isclass(cls):
            return 'classdef'
        elif inspect.ismodule(cls):
            return 'file_input'
        elif inspect.isbuiltin(cls) or inspect.ismethod(cls) or \
                inspect.ismethoddescriptor(cls):
            return 'funcdef'

    @underscore_memoization
    def _cls(self):
        """
        We used to limit the lookups for instantiated objects like list(), but
        this is not the case anymore. Python itself
        """
        # Ensures that a CompiledObject is returned that is not an instance (like list)
        return self

    def _get_class(self):
        if not fake.is_class_instance(self.obj) or \
                inspect.ismethoddescriptor(self.obj):  # slots
            return self.obj

        try:
            return self.obj.__class__
        except AttributeError:
            # happens with numpy.core.umath._UFUNC_API (you get it
            # automatically by doing `import numpy`.
            return type

    def get_filters(self, search_global=False, is_instance=False,
                    until_position=None, origin_scope=None):
        yield self._ensure_one_filter(is_instance)

    @memoize_method
    def _ensure_one_filter(self, is_instance):
        """
        search_global shouldn't change the fact that there's one dict, this way
        there's only one `object`.
        """
        return CompiledObjectFilter(self.evaluator, self, is_instance)

    def get_subscope_by_name(self, name):
        if name in dir(self.obj):
            return CompiledName(self.evaluator, self, name).parent
        else:
            raise KeyError("CompiledObject doesn't have an attribute '%s'." % name)

    @CheckAttribute
    def py__getitem__(self, index):
        if type(self.obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return set()

        return set([create(self.evaluator, self.obj[index])])

    @CheckAttribute
    def py__iter__(self):
        if type(self.obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return

        for part in self.obj:
            yield LazyKnownContext(create(self.evaluator, part))

    def py__name__(self):
        try:
            return self._get_class().__name__
        except AttributeError:
            return None

    @property
    def name(self):
        try:
            name = self._get_class().__name__
        except AttributeError:
            name = repr(self.obj)
        return CompiledContextName(self, name)

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
                bltn_obj = create(self.evaluator, bltn_obj)
                for result in self.evaluator.execute(bltn_obj, params):
                    yield result

    def is_scope(self):
        return True

    def get_self_attributes(self):
        return []  # Instance compatibility

    def get_imports(self):
        return []  # Builtins don't have imports


class CompiledName(AbstractNameDefinition):
    def __init__(self, evaluator, parent_context, name):
        self._evaluator = evaluator
        self.parent_context = parent_context
        self.string_name = name

    def __repr__(self):
        try:
            name = self.parent_context.name  # __name__ is not defined all the time
        except AttributeError:
            name = None
        return '<%s: (%s).%s>' % (self.__class__.__name__, name, self.string_name)

    @property
    def api_type(self):
        return next(iter(self.infer())).api_type

    @underscore_memoization
    def infer(self):
        module = self.parent_context.get_root_context()
        return [_create_from_name(self._evaluator, module, self.parent_context, self.string_name)]


class UnresolvableParamName(AbstractNameDefinition):
    api_type = 'param'

    def __init__(self, compiled_obj, name):
        self.parent_context = compiled_obj.parent_context
        self.string_name = name

    def infer(self):
        return set()


class CompiledContextName(ContextNameMixin, AbstractNameDefinition):
    def __init__(self, context, name):
        self.string_name = name
        self._context = context
        self.parent_context = context.parent_context


class EmptyCompiledName(AbstractNameDefinition):
    """
    Accessing some names will raise an exception. To avoid not having any
    completions, just give Jedi the option to return this object. It infers to
    nothing.
    """
    def __init__(self, evaluator, name):
        self.parent_context = evaluator.BUILTINS
        self.string_name = name

    def infer(self):
        return []


class CompiledObjectFilter(AbstractFilter):
    name_class = CompiledName

    def __init__(self, evaluator, compiled_object, is_instance=False):
        self._evaluator = evaluator
        self._compiled_object = compiled_object
        self._is_instance = is_instance

    @memoize_method
    def get(self, name):
        name = str(name)
        obj = self._compiled_object.obj
        try:
            getattr(obj, name)
            if self._is_instance and name not in dir(obj):
                return []
        except AttributeError:
            return []
        except Exception:
            # This is a bit ugly. We're basically returning this to make
            # lookups possible without having the actual attribute. However
            # this makes proper completion possible.
            return [EmptyCompiledName(self._evaluator, name)]
        return [self._create_name(name)]

    def values(self):
        obj = self._compiled_object.obj

        names = []
        for name in dir(obj):
            names += self.get(name)

        is_instance = self._is_instance or fake.is_class_instance(obj)
        # ``dir`` doesn't include the type names.
        if not inspect.ismodule(obj) and (obj is not type) and not is_instance:
            for filter in create(self._evaluator, type).get_filters():
                names += filter.values()
        return names

    def _create_name(self, name):
        return self.name_class(self._evaluator, self._compiled_object, name)


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

    # - Window
    # X:\path\to\lib-dynload/datetime.pyd => datetime
    module_path = fs_path[len(path):].lstrip(os.path.sep).lstrip('/')
    # - Window
    # Replace like X:\path\to\something/foo/bar.py
    return _path_re.sub('', module_path).replace(os.path.sep, '.').replace('/', '.')


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
        debug.warning('Module %s not importable in path %s.', dotted_path, path)
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


def _create_from_name(evaluator, module, compiled_object, name):
    obj = compiled_object.obj
    faked = None
    try:
        faked = fake.get_faked(evaluator, module, obj, parent_context=compiled_object, name=name)
        if faked.type == 'funcdef':
            from jedi.evaluate.representation import FunctionContext
            return FunctionContext(evaluator, compiled_object, faked)
    except fake.FakeDoesNotExist:
        pass

    try:
        obj = getattr(obj, name)
    except AttributeError:
        # Happens e.g. in properties of
        # PyQt4.QtGui.QStyleOptionComboBox.currentText
        # -> just set it to None
        obj = None
    return create(evaluator, obj, parent_context=compiled_object, faked=faked)


def builtin_from_name(evaluator, string):
    bltn_obj = getattr(_builtins, string)
    return create(evaluator, bltn_obj)


def _a_generator(foo):
    """Used to have an object to return for generators."""
    yield 42
    yield foo


_SPECIAL_OBJECTS = {
    'FUNCTION_CLASS': type(load_module),
    'METHOD_CLASS': type(CompiledObject.is_class),
    'MODULE_CLASS': type(os),
    'GENERATOR_OBJECT': _a_generator(1.0),
    'BUILTINS': _builtins,
}


def get_special_object(evaluator, identifier):
    obj = _SPECIAL_OBJECTS[identifier]
    return create(evaluator, obj, parent_context=create(evaluator, _builtins))


def compiled_objects_cache(attribute_name):
    def decorator(func):
        """
        This decorator caches just the ids, oopposed to caching the object itself.
        Caching the id has the advantage that an object doesn't need to be
        hashable.
        """
        def wrapper(evaluator, obj, parent_context=None, module=None, faked=None):
            cache = getattr(evaluator, attribute_name)
            # Do a very cheap form of caching here.
            key = id(obj), id(parent_context)
            try:
                return cache[key][0]
            except KeyError:
                # TODO this whole decorator is way too ugly
                result = func(evaluator, obj, parent_context, module, faked)
                # Need to cache all of them, otherwise the id could be overwritten.
                cache[key] = result, obj, parent_context, module, faked
                return result
        return wrapper

    return decorator


@compiled_objects_cache('compiled_cache')
def create(evaluator, obj, parent_context=None, module=None, faked=None):
    """
    A very weird interface class to this module. The more options provided the
    more acurate loading compiled objects is.
    """
    if inspect.ismodule(obj):
        if parent_context is not None:
            # Modules don't have parents, be careful with caching: recurse.
            return create(evaluator, obj)
    else:
        if parent_context is None and obj != _builtins:
            return create(evaluator, obj, create(evaluator, _builtins))

        try:
            faked = fake.get_faked(evaluator, module, obj, parent_context=parent_context)
            if faked.type == 'funcdef':
                from jedi.evaluate.representation import FunctionContext
                return FunctionContext(evaluator, parent_context, faked)
        except fake.FakeDoesNotExist:
            pass

    return CompiledObject(evaluator, obj, parent_context, faked)
