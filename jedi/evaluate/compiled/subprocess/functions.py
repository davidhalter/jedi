import sys
from jedi.evaluate.compiled import access


def get_sys_path():
    return sys.path


def load_module(evaluator, path=None, name=None):
    return access.load_module(evaluator, path=path, name=name)


def get_compiled_method_return(evaluator, id, attribute, *args, **kwargs):
    handle = evaluator.compiled_subprocess.get_access_handle(id)
    #print >> sys.stderr, handle, attribute, args, kwargs
    #print(id, attribute, args, kwargs, file=sys.stderr)
    return getattr(handle.access, attribute)(*args, **kwargs)


def get_special_object(evaluator, identifier):
    return access.get_special_object(evaluator, identifier)


def create_simple_object(evaluator, obj):
    return access.create_access_path(evaluator, obj)
