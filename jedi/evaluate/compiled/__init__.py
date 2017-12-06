from jedi._compatibility import builtins as _builtins
from jedi.evaluate.compiled.context import CompiledObject, CompiledName, \
    CompiledObjectFilter, CompiledContextName, create_from_access_path, \
    create_from_name
from jedi.evaluate.compiled import access


def builtin_from_name(evaluator, string):
    builtins = evaluator.get_builtins_module()
    return create_from_name(evaluator, builtins, string)


def create_simple_object(evaluator, obj):
    """
    Only allows creations of objects that are easily picklable across Python
    versions.
    """
    assert isinstance(obj, (int, float, str, bytes, slice, complex, type(Ellipsis)))
    return create_from_access_path(
        evaluator,
        evaluator.compiled_subprocess.create_simple_object(obj)
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
