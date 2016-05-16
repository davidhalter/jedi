"""
Used only for REPL Completion.
"""

import inspect

from jedi.parser import load_grammar
from jedi.parser.fast import FastParser
from jedi.evaluate import compiled


class MixedObject(object):
    """
    A ``MixedObject`` is used in two ways:

    1. It uses the default logic of ``parser.tree`` objects,
    2. except for getattr calls. The names dicts are generated in a fashion
       like ``CompiledObject``.

    This combined logic makes it possible to provide more powerful REPL
    completion. It allows side effects that are not noticable with the default
    parser structure to still be completeable.
    """
    def __init__(self, evaluator, obj):
        self._evaluator = evaluator
        self.obj = obj


def _load_module(evaluator, path, python_object):
    module = FastParser(evaluator.grammar, path=path).module
    python_module = inspect.getmodule(python_object)

    evaluator.modules[python_module.__name__] = module
    return module


def find_syntax_node(evaluator, python_object):
    path = inspect.getsourcefile(python_object)
    if path is None:
        return None

    module = _load_module(evaluator, path, python_object)
    if inspect.ismodule(python_object):
        return module

    try:
        code = python_object.__code__
    except AttributeError:
        # By using the line number of a code object we make the lookup in a
        # file pretty easy. There's still a possibility of people defining
        # stuff like ``a = 3; foo(a); a = 4`` on the same line, but if people
        # do so we just don't care.
        line_nr = code.co_firstlineno
    return None


@compiled_objects_cache
def create(evaluator, obj):
    node = find_syntax_node(obj)
    if node is None:
        return compiled.create(evaluator, obj)
    else:
        return MixedObject(evaluator, obj)
