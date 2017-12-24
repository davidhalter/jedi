import sys
import os
import imp

from jedi._compatibility import find_module, cast_path
from jedi.evaluate.compiled import access
from jedi import parser_utils


def get_sys_path():
    return list(map(cast_path, sys.path))


def load_module(evaluator, **kwargs):
    return access.load_module(evaluator, **kwargs)


def get_compiled_method_return(evaluator, id, attribute, *args, **kwargs):
    handle = evaluator.compiled_subprocess.get_access_handle(id)
    # print >> sys.stderr, handle, attribute, args, kwargs
    # print(id, attribute, args, kwargs, file=sys.stderr)
    return getattr(handle.access, attribute)(*args, **kwargs)


def get_special_object(evaluator, identifier):
    return access.get_special_object(evaluator, identifier)


def create_simple_object(evaluator, obj):
    return access.create_access_path(evaluator, obj)


def get_module_info(evaluator, sys_path=None, full_name=None, **kwargs):
    if sys_path is not None:
        sys.path, temp = sys_path, sys.path
    try:
        module_file, module_path, is_pkg = find_module(full_name=full_name, **kwargs)
    except ImportError:
        return None, None, None
    finally:
        if sys_path is not None:
            sys.path = temp

    code = None
    if is_pkg:
        # In this case, we don't have a file yet. Search for the
        # __init__ file.
        if module_path.endswith(('.zip', '.egg')):
            code = module_file.loader.get_source(full_name)
        else:
            module_path = _get_init_path(module_path)
    elif module_file:
        code = module_file.read()
        module_file.close()

    return code, cast_path(module_path), is_pkg


def _get_init_path(directory_path):
    """
    The __init__ file can be searched in a directory. If found return it, else
    None.
    """
    for suffix, _, _ in imp.get_suffixes():
        path = os.path.join(directory_path, '__init__' + suffix)
        if os.path.exists(path):
            return path
    return None


def safe_literal_eval(evaluator, value):
    return parser_utils.safe_literal_eval(value)
