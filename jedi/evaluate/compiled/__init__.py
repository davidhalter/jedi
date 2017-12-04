import types

from jedi._compatibility import builtins as _builtins
from jedi.evaluate.compiled.context import CompiledObject, CompiledName, \
    CompiledObjectFilter, CompiledContextName, create_from_access_path
from jedi.evaluate.compiled import access


def builtin_from_name(evaluator, string):
    bltn_obj = getattr(_builtins, string)
    return create(evaluator, bltn_obj)


def create_simple_object(evaluator, obj):
    """
    Only allows creations of objects that are easily picklable across Python
    versions.
    """
    assert isinstance(obj, (int, float, str, bytes, slice, complex, type(Ellipsis)))
    return create(evaluator, obj)


def create(evaluator, obj):
    return create_from_access_path(
        evaluator, access.create_access_path(evaluator, obj)
    )


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
    return create(evaluator, obj)


def load_module(evaluator, path=None, name=None):
    return create_from_access_path(
        evaluator,
        access.load_module(evaluator, path=path, name=name)
    )
