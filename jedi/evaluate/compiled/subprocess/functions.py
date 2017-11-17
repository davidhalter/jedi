import sys
from jedi.evaluate import compiled


def get_sys_path():
    return sys.path


def import_module(evaluator, handles, path=None, name=None):
    compiled_object = compiled.load_module(evaluator, path=path, name=name)
    if compiled_object is None:
        return None
    return handles.create(compiled_object)


def get_compiled_property(evaluator, handles, id, attribute):
    compiled_object = handles.get_compiled_object(id)
    return getattr(compiled_object, attribute)


def get_compiled_method_return(evaluator, handles, id, attribute, *args, **kwargs):
    compiled_object = handles.get_compiled_object(id)
    return getattr(compiled_object, attribute)(*args, **kwargs)
