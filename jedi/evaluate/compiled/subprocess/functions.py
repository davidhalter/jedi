import sys
from jedi.evaluate import compiled


def get_sys_path():
    return sys.path


def import_module(evaluator, handles, path=None, name=None):
    compiled_object = compiled.load_module(evaluator, path=path, name=name)
    if compiled_object is None:
        return None
    return handles.create(compiled_object)


def get_compiled_method_return(evaluator, id, attribute, *args, **kwargs):
    handle = evaluator.compiled_subprocess.get_access_handle(id)
    return getattr(handle.access, attribute)(*args, **kwargs)


def get_special_object(evaluator, handles, identifier):
    return compiled.get_special_object(evaluator, identifier)
