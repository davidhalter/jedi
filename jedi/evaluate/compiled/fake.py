"""
Loads functions that are mixed in to the standard library. E.g. builtins are
written in C (binaries), but my autocompletion only understands Python code. By
mixing in Python code, the autocompletion should work much better for builtins.
"""

import re
import os
import inspect

from jedi._compatibility import is_py3k, builtins
from jedi.parser import Parser
from jedi.parser.representation import Class
from jedi.evaluate.helpers import FakeName

modules = {}


def _load_fakes(module_name):
    regex = r'^(def|class)\s+([\w\d]+)'

    def process_code(code, depth=0):
        funcs = {}
        matches = list(re.finditer(regex, code, re.MULTILINE))
        positions = [m.start() for m in matches]
        for i, pos in enumerate(positions):
            try:
                code_block = code[pos:positions[i + 1]]
            except IndexError:
                code_block = code[pos:len(code)]
            structure_name = matches[i].group(1)
            name = matches[i].group(2)
            if structure_name == 'def':
                funcs[name] = code_block
            elif structure_name == 'class':
                if depth > 0:
                    raise NotImplementedError()

                # remove class line
                c = re.sub(r'^[^\n]+', '', code_block)
                # remove whitespace
                c = re.compile(r'^[ ]{4}', re.MULTILINE).sub('', c)

                funcs[name] = process_code(c)
            else:
                raise NotImplementedError()
        return funcs

    if module_name == '__builtin__' and not is_py3k:
        module_name = 'builtins'
    path = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(path, 'mixin', module_name) + '.pym') as f:
            s = f.read()
    except IOError:
        return {}
    else:
        mixin_dct = process_code(s)
        if is_py3k and module_name == 'builtins':
            # in the case of Py3k xrange is now range
            mixin_dct['range'] = mixin_dct['xrange']
        return mixin_dct


def _load_faked_module(module):
    module_name = module.__name__
    if module_name == '__builtin__' and not is_py3k:
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

        if module_name == 'builtins' and not is_py3k:
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


def _faked(module, obj, name=None):
    # Crazy underscore actions to try to escape all the internal madness.
    obj = obj.__class__ if is_class_instance(obj) else obj
    if module is None:
        try:
            module = obj.__objclass__
        except AttributeError:
            pass

        try:
            imp_plz = obj.__module__
        except AttributeError:
            # Unfortunately in some cases like `int` there's no __module__
            module = builtins
        else:
            module = __import__(imp_plz)

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


def get_faked(*args, **kwargs):
    result = _faked(*args, **kwargs)
    if not isinstance(result, Class):
        return result


def is_class_instance(obj):
    """Like inspect.* methods."""
    return not (inspect.isclass(obj) or inspect.ismodule(obj)
                or inspect.isbuiltin(obj) or inspect.ismethod(obj)
                or inspect.ismethoddescriptor(obj))
