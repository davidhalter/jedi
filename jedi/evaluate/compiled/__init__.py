"""
Imitate the parser representation.
"""
import inspect
import re
import sys
import os
import types
from functools import partial

from jedi._compatibility import builtins as _builtins
from jedi import debug
from jedi.cache import underscore_memoization, memoize_method
from jedi.evaluate.filters import AbstractFilter, AbstractNameDefinition, \
    ContextNameMixin
from jedi.evaluate.base_context import Context, ContextSet
from jedi.evaluate.lazy_context import LazyKnownContext
from jedi.evaluate.compiled.access import DirectObjectAccess, _sentinel, create_access
from jedi.evaluate.cache import evaluator_function_cache
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
        if instance is None:
            return self

        # This might raise an AttributeError. That's wanted.
        if self.check_name == '__iter__':
            # Python iterators are a bit strange, because there's no need for
            # the __iter__ function as long as __getitem__ is defined (it will
            # just start with __getitem__(0). This is especially true for
            # Python 2 strings, where `str.__iter__` is not even defined.
            if not instance.access.has_iter():
                raise AttributeError
        else:
            instance.access.getattr(self.check_name)
        return partial(self.func, instance)


class CompiledObject(Context):
    path = None  # modules have this attribute - set it to None.
    used_names = lambda self: {}  # To be consistent with modules.

    def __init__(self, evaluator, access, parent_context=None, faked_class=None):
        super(CompiledObject, self).__init__(evaluator, parent_context)
        self.access = access
        # This attribute will not be set for most classes, except for fakes.
        self.tree_node = faked_class

    def get_root_node(self):
        # To make things a bit easier with filters we add this method here.
        return self.get_root_context()

    @CheckAttribute
    def py__call__(self, params):
        if self.tree_node is not None and self.tree_node.type == 'funcdef':
            from jedi.evaluate.context.function import FunctionContext
            return FunctionContext(
                self.evaluator,
                parent_context=self.parent_context,
                funcdef=self.tree_node
            ).py__call__(params)
        if self.access.is_class():
            from jedi.evaluate.context import CompiledInstance
            return ContextSet(CompiledInstance(self.evaluator, self.parent_context, self, params))
        else:
            return ContextSet.from_iterable(self._execute_function(params))

    @CheckAttribute
    def py__class__(self):
        return create_from_access(self.evaluator, self.access.py__class__())

    @CheckAttribute
    def py__mro__(self):
        return (self,) + tuple(
            create_from_access(self.evaluator, access) for access in self.access.py__mro__accesses()
        )

    @CheckAttribute
    def py__bases__(self):
        return tuple(
            create_from_access(self.evaluator, access)
            for access in self.access.py__bases__()
        )

    def py__bool__(self):
        return self.access.py__bool__()

    def py__file__(self):
        return self.access.py__file__()

    def is_class(self):
        return self.access.is_class()

    def py__doc__(self, include_call_signature=False):
        return self.access.py__doc__()

    def get_param_names(self):
        try:
            signature_params = self.access.get_signature_params()
        except ValueError:  # Has no signature
            params_str, ret = self._parse_function_doc()
            tokens = params_str.split(',')
            if self.access.ismethoddescriptor():
                tokens.insert(0, 'self')
            for p in tokens:
                parts = p.strip().split('=')
                yield UnresolvableParamName(self, parts[0])
        else:
            for signature_param in signature_params:
                yield SignatureParamName(self, signature_param)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.access.get_repr())

    @underscore_memoization
    def _parse_function_doc(self):
        doc = self.py__doc__()
        if doc is None:
            return '', ''

        return _parse_function_doc(doc)

    @property
    def api_type(self):
        return self.access.get_api_type()

    @underscore_memoization
    def _cls(self):
        """
        We used to limit the lookups for instantiated objects like list(), but
        this is not the case anymore. Python itself
        """
        # Ensures that a CompiledObject is returned that is not an instance (like list)
        return self

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

    @CheckAttribute
    def py__getitem__(self, index):
        access = self.access.py__getitem__(index)
        if access is None:
            return ContextSet()

        return ContextSet(create_from_access(self.evaluator, access))

    @CheckAttribute
    def py__iter__(self):
        for access in self.access.py__iter__list():
            yield LazyKnownContext(create_from_access(self.evaluator, access))

    def py__name__(self):
        return self.access.py__name__()

    @property
    def name(self):
        name = self.py__name__()
        if name is None:
            name = self.access.get_repr()
        return CompiledContextName(self, name)

    def _execute_function(self, params):
        from jedi.evaluate import docstrings
        if self.api_type != 'function':
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
                for result in bltn_obj.execute(params):
                    yield result
        for type_ in docstrings.infer_return_types(self):
            yield type_

    def get_self_attributes(self):
        return []  # Instance compatibility

    def get_imports(self):
        return []  # Builtins don't have imports

    def dict_values(self):
        return ContextSet.from_iterable(
            create_from_access(self.evaluator, access) for access in self.access.dict_values()
        )

    def get_safe_value(self, default=_sentinel):
        try:
            return self.access.get_safe_value()
        except ValueError:
            if default == _sentinel:
                raise
            return default

    def execute_operation(self, other, operator):
        return create_from_access(
            self.evaluator,
            self.access.execute_operation(other.access, operator)
        )

    def negate(self):
        return create_from_access(self.evaluator, self.access.negate())

    def is_super_class(self, exception):
        return self.access.is_super_class(exception)


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
        return ContextSet(_create_from_name(
            self._evaluator, self.parent_context, self.string_name
        ))


class SignatureParamName(AbstractNameDefinition):
    api_type = 'param'

    def __init__(self, compiled_obj, signature_param):
        self.parent_context = compiled_obj.parent_context
        self._signature_param = signature_param

    @property
    def string_name(self):
        return self._signature_param.name

    def infer(self):
        p = self._signature_param
        evaluator = self.parent_context.evaluator
        contexts = ContextSet()
        if p.has_default:
            contexts = ContextSet(create_from_access(evaluator, p.default))
        if p.has_annotation:
            annotation = create_from_access(evaluator, p.annotation)
            contexts |= annotation.execute_evaluated()
        return contexts


class UnresolvableParamName(AbstractNameDefinition):
    api_type = 'param'

    def __init__(self, compiled_obj, name):
        self.parent_context = compiled_obj.parent_context
        self.string_name = name

    def infer(self):
        return ContextSet()


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
        return ContextSet()


class CompiledObjectFilter(AbstractFilter):
    name_class = CompiledName

    def __init__(self, evaluator, compiled_object, is_instance=False):
        self._evaluator = evaluator
        self._compiled_object = compiled_object
        self._is_instance = is_instance

    @memoize_method
    def get(self, name):
        name = str(name)
        try:
            if not self._compiled_object.access.is_allowed_getattr(name):
                return [EmptyCompiledName(self._evaluator, name)]
        except AttributeError:
            return []

        if self._is_instance and name not in self._compiled_object.access.dir():
            return []
        return [self._create_name(name)]

    def values(self):
        names = []
        for name in self._compiled_object.access.dir():
            names += self.get(name)

        # ``dir`` doesn't include the type names.
        if not self._is_instance and self._compiled_object.access.needs_type_completions():
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
    sys_path = list(evaluator.project.sys_path)
    if path is not None:
        dotted_path = dotted_from_fs_path(path, sys_path=sys_path)
    else:
        dotted_path = name

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


def _create_from_name(evaluator, compiled_object, name):
    faked = None
    try:
        faked = fake.get_faked_with_parent_context(compiled_object, name)
    except fake.FakeDoesNotExist:
        pass

    access = compiled_object.access.getattr(name, default=None)
    return create_from_access(evaluator, access, parent_context=compiled_object, faked=faked)


def builtin_from_name(evaluator, string):
    bltn_obj = getattr(_builtins, string)
    return create(evaluator, bltn_obj)


def _a_generator(foo):
    """Used to have an object to return for generators."""
    yield 42
    yield foo


_SPECIAL_OBJECTS = {
    'FUNCTION_CLASS': types.FunctionType,
    'METHOD_CLASS': type(CompiledObject.is_class),
    'MODULE_CLASS': types.ModuleType,
    'GENERATOR_OBJECT': _a_generator(1.0),
    'BUILTINS': _builtins,
}


def get_special_object(evaluator, identifier):
    obj = _SPECIAL_OBJECTS[identifier]
    if identifier == 'BUILTINS':
        parent_context = None
    else:
        parent_context = create(evaluator, _builtins)
    return create(evaluator, obj, parent_context=parent_context)


def _normalize_create_args(func):
    """The cache doesn't care about keyword vs. normal args."""
    def wrapper(evaluator, obj, parent_context=None, faked=None):
        return func(evaluator, obj, parent_context, faked)
    return wrapper


def create(evaluator, obj, parent_context=None, faked=None):
    if inspect.ismodule(obj):
        if parent_context is not None:
            # Modules don't have parents, be careful with caching: recurse.
            return create(evaluator, obj)

    return create_from_access(evaluator, create_access(evaluator, obj), parent_context, faked)


@_normalize_create_args
@evaluator_function_cache()
def create_from_access(evaluator, access, parent_context=None, faked=None):
    """
    A very weird interface class to this module. The more options provided the
    more acurate loading compiled objects is.
    """
    if parent_context is None and faked is None:
        access_tuples = access.get_access_path_tuples()
        if access_tuples:
            string_names, accesses = zip(*access_tuples)
            try:
                tree_nodes = fake.get_faked_tree_nodes(evaluator.latest_grammar, string_names)
            except fake.FakeDoesNotExist:
                pass
            else:
                for access2, tree_node in zip(accesses, tree_nodes):
                    parent_context = create_from_access(
                        evaluator, access2, parent_context, faked=tree_node
                    )
                return parent_context

        parent_context = create(evaluator, _builtins)
        return create_from_access(evaluator, access, parent_context)

    return CompiledObject(evaluator, access, parent_context, faked)
