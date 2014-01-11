"""
Loads functions that are mixed in to the standard library. E.g. builtins are
written in C (binaries), but my autocompletion only understands Python code. By
mixing in Python code, the autocompletion should work much better for builtins.
"""

import re
import os
import inspect

from jedi._compatibility import is_py3k
from jedi.parser import Parser

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

    # sometimes there are stupid endings like `_sqlite3.cpython-32mu`
    module_name = re.sub(r'\..*', '', module_name)

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


def _load_module(module):
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
            return
        module = Parser(source, module_name).module
        modules[module_name] = module
        return module


def get_faked(module, obj):
    def from_scope(scope, obj):
        for s in scope.subscopes:
            if str(s.name) == obj.__name__:
                return s

    mod = _load_module(module)
    if mod is None:
        return

    # Having the module as a `parser.representation.module`, we need to scan
    # for methods.
    if is_class_instance(obj):
        obj = obj.__class__
    if inspect.isbuiltin(obj):
        return from_scope(mod, obj)
    elif not inspect.isclass(obj):
        # object is a method or descriptor
        cls = from_scope(mod, obj.__objclass__)
        if cls is None:
            return
        return from_scope(cls, obj)


def is_class_instance(obj):
    """Like inspect.* methods."""
    return not (inspect.isclass(obj) or inspect.ismodule(obj)
                or inspect.isbuiltin(obj) or inspect.ismethod(obj)
                or inspect.ismethoddescriptor(obj))
