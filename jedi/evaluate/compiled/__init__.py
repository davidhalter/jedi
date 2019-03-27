from jedi._compatibility import unicode
from jedi.evaluate.compiled.context import CompiledObject, CompiledName, \
    CompiledObjectFilter, CompiledContextName, create_from_access_path, \
    create_from_name
from jedi.evaluate.base_context import ContextWrapper
from jedi.evaluate.helpers import execute_evaluated


def builtin_from_name(evaluator, string):
    builtins = evaluator.builtins_module
    filter_ = next(builtins.get_filters())
    name, = filter_.get(string)
    context, = name.infer()
    return context


class CompiledValue(ContextWrapper):
    def __init__(self, instance, compiled_obj):
        super(CompiledValue, self).__init__(instance)
        self._compiled_obj = compiled_obj

    def __getattribute__(self, name):
        if name in ('get_safe_value', 'execute_operation', 'access_handle',
                    'negate', 'py__bool__'):
            return getattr(self._compiled_obj, name)
        return super(CompiledValue, self).__getattribute__(name)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._compiled_obj)


def create_simple_object(evaluator, obj):
    """
    Only allows creations of objects that are easily picklable across Python
    versions.
    """
    assert type(obj) in (int, float, str, bytes, unicode, slice, complex, bool), obj
    compiled_obj = create_from_access_path(
        evaluator,
        evaluator.compiled_subprocess.create_simple_object(obj)
    )
    instance, = builtin_from_name(evaluator, compiled_obj.name.string_name).execute()
    return CompiledValue(instance, compiled_obj)


def get_special_object(evaluator, identifier):
    return create_from_access_path(
        evaluator,
        evaluator.compiled_subprocess.get_special_object(identifier)
    )


def get_string_context_set(evaluator):
    return execute_evaluated(builtin_from_name(evaluator, u'str'))


def load_module(evaluator, dotted_name, **kwargs):
    # Temporary, some tensorflow builtins cannot be loaded, so it's tried again
    # and again and it's really slow.
    if dotted_name.startswith('tensorflow.'):
        return None
    access_path = evaluator.compiled_subprocess.load_module(dotted_name=dotted_name, **kwargs)
    if access_path is None:
        return None
    return create_from_access_path(evaluator, access_path)
