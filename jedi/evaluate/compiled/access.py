import inspect
import types
import operator as op

from jedi._compatibility import unicode, is_py3, is_py34, builtins
from jedi.evaluate.compiled.getattr_static import getattr_static


MethodDescriptorType = type(str.replace)
# These are not considered classes and access is granted even though they have
# a __class__ attribute.
NOT_CLASS_TYPES = (
    types.BuiltinFunctionType,
    types.CodeType,
    types.FrameType,
    types.FunctionType,
    types.GeneratorType,
    types.GetSetDescriptorType,
    types.LambdaType,
    types.MemberDescriptorType,
    types.MethodType,
    types.ModuleType,
    types.TracebackType,
    MethodDescriptorType
)

if is_py3:
    NOT_CLASS_TYPES += (
        types.MappingProxyType,
        types.SimpleNamespace
    )
    if is_py34:
        NOT_CLASS_TYPES += (types.DynamicClassAttribute,)


# Those types don't exist in typing.
MethodDescriptorType = type(str.replace)
WrapperDescriptorType = type(set.__iter__)
# `object.__subclasshook__` is an already executed descriptor.
object_class_dict = type.__dict__["__dict__"].__get__(object)
ClassMethodDescriptorType = type(object_class_dict['__subclasshook__'])

ALLOWED_DESCRIPTOR_ACCESS = (
    types.FunctionType,
    types.GetSetDescriptorType,
    types.MemberDescriptorType,
    MethodDescriptorType,
    WrapperDescriptorType,
    ClassMethodDescriptorType,
    staticmethod,
    classmethod,
)

_sentinel = object()

# Maps Python syntax to the operator module.
COMPARISON_OPERATORS = {
    '==': op.eq,
    '!=': op.ne,
    'is': op.is_,
    'is not': op.is_not,
    '<': op.lt,
    '<=': op.le,
    '>': op.gt,
    '>=': op.ge,
}

_OPERATORS = {
    '+': op.add,
    '-': op.sub,
}
_OPERATORS.update(COMPARISON_OPERATORS)




class DirectObjectAccess(object):
    def __init__(self, obj):
        self._obj = obj

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._obj)

    def _create_access(self, obj):
        return DirectObjectAccess(obj)

    def py__bool__(self):
        return bool(self._obj)

    def py__file__(self):
        try:
            return self._obj.__file__
        except AttributeError:
            return None

    def py__doc__(self, include_call_signature=False):
        return inspect.getdoc(self._obj) or ''

    def py__name__(self):
        if not is_class_instance(self._obj) or \
                inspect.ismethoddescriptor(self._obj):  # slots
            cls = self._obj
        else:
            try:
                cls = self._obj.__class__
            except AttributeError:
                # happens with numpy.core.umath._UFUNC_API (you get it
                # automatically by doing `import numpy`.
                return None

        try:
            return cls.__name__
        except AttributeError:
            return None

    def py__mro__accesses(self):
        return tuple(self._create_access(cls) for cls in self._obj.__mro__[1:])

    def py__getitem__(self, index):
        if type(self._obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return None

        return self._create_access(self._obj[index])

    def py__iter__list(self):
        if type(self._obj) not in (str, list, tuple, unicode, bytes, bytearray, dict):
            # Get rid of side effects, we won't call custom `__getitem__`s.
            return []

        lst = []
        for i, part in enumerate(self._obj):
            if i > 20:
                # Should not go crazy with large iterators
                break
            lst.append(self._create_access(part))
        return lst

    def get_repr(self):
        return repr(self._obj)

    def is_class(self):
        return inspect.isclass(self._obj)

    def dir(self):
        return dir(self._obj)

    def has_iter(self):
        try:
            iter(self._obj)
            return True
        except TypeError:
            return False

    def is_allowed_getattr(self, name):
        try:
            attr, is_get_descriptor = getattr_static(self._obj, name)
        except AttributeError:
            return []
        else:
            if is_get_descriptor \
                    and not type(attr) in ALLOWED_DESCRIPTOR_ACCESS:
                # In case of descriptors that have get methods we cannot return
                # it's value, because that would mean code execution.
                return False
        return True

    def getattr(self, name, default=_sentinel):
        try:
            return self._create_access(getattr(self._obj, name))
        except AttributeError:
            # Happens e.g. in properties of
            # PyQt4.QtGui.QStyleOptionComboBox.currentText
            # -> just set it to None
            if default is _sentinel:
                raise
            return None

    def get_safe_value(self, default=_sentinel):
        if type(self._obj) in (float, int, str, unicode, slice, type(Ellipsis)):
            return self._obj
        if default == _sentinel:
            raise ValueError

    def get_api_type(self):
        obj = self._obj
        if self.is_class():
            return 'class'
        elif inspect.ismodule(obj):
            return 'module'
        elif inspect.isbuiltin(obj) or inspect.ismethod(obj) \
                or inspect.ismethoddescriptor(obj) or inspect.isfunction(obj):
            return 'function'
        # Everything else...
        return 'instance'

    def get_access_path_tuples(self):
        path = self._get_objects_path()
        try:
            # Just provoke an AttributeError.
            result = [(o.__name__, o) for o in path]
        except AttributeError:
            return []
        else:
            return [(name, self._create_access(o)) for name, o in result]

    def _get_objects_path(self):
        def get():
            obj = self._obj
            yield obj
            try:
                obj = obj.__objclass__
            except AttributeError:
                pass
            else:
                yield obj

            try:
                # Returns a dotted string path.
                imp_plz = obj.__module__
            except AttributeError:
                # Unfortunately in some cases like `int` there's no __module__
                if not inspect.ismodule(obj):
                    yield builtins
            else:
                if imp_plz is None:
                    # Happens for example in `(_ for _ in []).send.__module__`.
                    yield builtins
                else:
                    try:
                        yield __import__(imp_plz)
                    except ImportError:
                        # __module__ can be something arbitrary that doesn't exist.
                        yield builtins

        return list(reversed(list(get())))

    def execute_operation(self, other, operator):
        op = _OPERATORS[operator]
        return self._create_access(op(self._obj, other._obj))

    def needs_type_completions(self):
        return inspect.isclass(self._obj) and self._obj != type


def is_class_instance(obj):
    """Like inspect.* methods."""
    try:
        cls = obj.__class__
    except AttributeError:
        return False
    else:
        return cls != type and not issubclass(cls, NOT_CLASS_TYPES)
