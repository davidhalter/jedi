"""
Loads functions that are mixed in to the standard library. E.g. builtins are
written in C (binaries), but my autocompletion only understands Python code. By
mixing in Python code, the autocompletion should work much better for builtins.
"""

import os
import inspect

from jedi._compatibility import is_py3, builtins
from jedi.parser import Parser
from jedi.parser import token as token_pr
from jedi.parser.representation import Class
from jedi.evaluate.helpers import FakeName

modules = {}


def _load_faked_module(module):
    module_name = module.__name__
    if module_name == '__builtin__' and not is_py3:
        module_name = 'builtins'

    try:
        return modules[module_name]
    except KeyError:
        path = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(path, 'fake', module_name) + '.pym') as f:
                source = f.read()
        except IOError:
            modules[module_name] = None
            return
        module = Parser(source, module_name).module
        modules[module_name] = module

        if module_name == 'builtins' and not is_py3:
            # There are two implementations of `open` for either python 2/3.
            # -> Rename the python2 version (`look at fake/builtins.pym`).
            open_func = search_scope(module, 'open')
            open_func.name = FakeName('open_python3')
            open_func = search_scope(module, 'open_python2')
            open_func.name = FakeName('open')
        return module


def search_scope(scope, obj_name):
    for s in scope.subscopes:
        if str(s.name) == obj_name:
            return s


def get_module(obj):
    if inspect.ismodule(obj):
        return obj
    try:
        obj = obj.__objclass__
    except AttributeError:
        pass

    try:
        imp_plz = obj.__module__
    except AttributeError:
        # Unfortunately in some cases like `int` there's no __module__
        return builtins
    else:
        return __import__(imp_plz)


def _faked(module, obj, name):
    # Crazy underscore actions to try to escape all the internal madness.
    if module is None:
        module = get_module(obj)

    faked_mod = _load_faked_module(module)
    if faked_mod is None:
        return

    # Having the module as a `parser.representation.module`, we need to scan
    # for methods.
    if name is None:
        if inspect.isbuiltin(obj):
            return search_scope(faked_mod, obj.__name__)
        elif not inspect.isclass(obj):
            # object is a method or descriptor
            cls = search_scope(faked_mod, obj.__objclass__.__name__)
            if cls is None:
                return
            return search_scope(cls, obj.__name__)
    else:
        if obj == module:
            return search_scope(faked_mod, name)
        else:
            cls = search_scope(faked_mod, obj.__name__)
            if cls is None:
                return
            return search_scope(cls, name)


def get_faked(module, obj, name=None):
    obj = obj.__class__ if is_class_instance(obj) else obj
    result = _faked(module, obj, name)
    if not isinstance(result, Class) and result is not None:
        # Set the docstr which was previously not set (faked modules don't
        # contain it).
        result.docstr = None
        if obj.__doc__:
            result.docstr = token_pr.TokenDocstring.fake_docstring(obj.__doc__)
        return result


def is_class_instance(obj):
    """Like inspect.* methods."""
    return not (inspect.isclass(obj) or inspect.ismodule(obj)
                or inspect.isbuiltin(obj) or inspect.ismethod(obj)
                or inspect.ismethoddescriptor(obj) or inspect.iscode(obj)
                or inspect.isgenerator(obj))
