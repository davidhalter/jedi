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


def get_special_object(evaluator, identifier):
    return create_from_access_path(
        evaluator,
        evaluator.compiled_subprocess.get_special_object(identifier)
    )


def load_module(evaluator, path=None, name=None):
    return create_from_access_path(
        evaluator,
        evaluator.compiled_subprocess.load_module(path=path, name=name)
    )
