"""
Loads functions that are mixed in to the standard library. E.g. builtins are
written in C (binaries), but my autocompletion only understands Python code. By
mixing in Python code, the autocompletion should work much better for builtins.
"""

import os
import inspect
from itertools import chain

from parso.python import tree

from jedi._compatibility import is_py3, builtins, unicode

fake_modules = {}


def _get_path_dict():
    path = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(path, 'fake')
    dct = {}
    for file_name in os.listdir(base_path):
        if file_name.endswith('.pym'):
            dct[file_name[:-4]] = os.path.join(base_path, file_name)
    return dct


_path_dict = _get_path_dict()


class FakeDoesNotExist(Exception):
    pass


def _load_faked_module(grammar, module_name):
    if module_name == '__builtin__' and not is_py3:
        module_name = 'builtins'

    try:
        return fake_modules[module_name]
    except KeyError:
        pass

    try:
        path = _path_dict[module_name]
    except KeyError:
        fake_modules[module_name] = None
        return

    with open(path) as f:
        source = f.read()

    fake_modules[module_name] = m = grammar.parse(unicode(source))

    if module_name == 'builtins' and not is_py3:
        # There are two implementations of `open` for either python 2/3.
        # -> Rename the python2 version (`look at fake/builtins.pym`).
        open_func = _search_scope(m, 'open')
        open_func.children[1].value = 'open_python3'
        open_func = _search_scope(m, 'open_python2')
        open_func.children[1].value = 'open'
    return m


def _search_scope(scope, obj_name):
    for s in chain(scope.iter_classdefs(), scope.iter_funcdefs()):
        if s.name.value == obj_name:
            return s


def _faked(grammar, module, obj, name):
    # Crazy underscore actions to try to escape all the internal madness.
    if module is None:
        module = _get_module(obj)

    faked_mod = _load_faked_module(grammar, module)
    if faked_mod is None:
        return None, None

    # Having the module as a `parser.python.tree.Module`, we need to scan
    # for methods.
    if name is None:
        if inspect.isbuiltin(obj) or inspect.isclass(obj):
            return _search_scope(faked_mod, obj.__name__), faked_mod
        elif not inspect.isclass(obj):
            # object is a method or descriptor
            try:
                objclass = obj.__objclass__
            except AttributeError:
                return None, None
            else:
                cls = _search_scope(faked_mod, objclass.__name__)
                if cls is None:
                    return None, None
                return _search_scope(cls, obj.__name__), faked_mod
    else:
        if obj is module:
            return _search_scope(faked_mod, name), faked_mod
        else:
            try:
                cls_name = obj.__name__
            except AttributeError:
                return None, None
            cls = _search_scope(faked_mod, cls_name)
            if cls is None:
                return None, None
            return _search_scope(cls, name), faked_mod
    return None, None


def _memoize_faked(obj):
    """
    A typical memoize function that ignores issues with non hashable results.
    """
    cache = obj.cache = {}

    def memoizer(*args, **kwargs):
        key = (obj, args, frozenset(kwargs.items()))
        try:
            result = cache[key]
        except (TypeError, ValueError):
            return obj(*args, **kwargs)
        except KeyError:
            result = obj(*args, **kwargs)
            if result is not None:
                cache[key] = obj(*args, **kwargs)
            return result
        else:
            return result
    return memoizer


@_memoize_faked
def _get_faked(grammar, module, obj, name=None):
    result, fake_module = _faked(grammar, module, obj, name)
    if result is None:
        # We're not interested in classes. What we want is functions.
        raise FakeDoesNotExist
    elif result.type == 'classdef':
        return result, fake_module
    else:
        # Set the docstr which was previously not set (faked modules don't
        # contain it).
        assert result.type == 'funcdef'
        doc = '"""%s"""' % obj.__doc__  # TODO need escapes.
        suite = result.children[-1]
        string = tree.String(doc, (0, 0), '')
        new_line = tree.Newline('\n', (0, 0))
        docstr_node = tree.PythonNode('simple_stmt', [string, new_line])
        suite.children.insert(1, docstr_node)
        return result, fake_module


def get_faked_with_parent_context(parent_context, name):
    if parent_context.tree_node is not None:
        # Try to search in already clearly defined stuff.
        found = _search_scope(parent_context.tree_node, name)
        if found is not None:
            return found
    raise FakeDoesNotExist


def get_faked_tree_nodes(grammar, string_names):
    module = base = _load_faked_module(grammar, string_names[0])
    if module is None:
        raise FakeDoesNotExist

    tree_nodes = [module]
    for name in string_names[1:]:
        base = _search_scope(base, name)
        if base is None:
            raise FakeDoesNotExist
        tree_nodes.append(base)
    return tree_nodes
