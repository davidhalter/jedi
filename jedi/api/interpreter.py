import inspect
import re

from jedi._compatibility import builtins
from jedi import debug
from jedi.common import source_to_unicode
from jedi.cache import underscore_memoization
from jedi.evaluate import compiled
from jedi.evaluate.compiled.fake import get_module
from jedi.parser import representation as pr
from jedi.parser.fast import FastParser
from jedi.evaluate import helpers


class InterpreterNamespace(pr.Module):
    def __init__(self, evaluator, namespace, parser_module):
        self.namespace = namespace
        self.parser_module = parser_module
        self._evaluator = evaluator

    def get_defined_names(self):
        for name in self.parser_module.get_defined_names():
            yield name
        for key, value in self.namespace.items():
            yield LazyName(self._evaluator, key, value)

    def __getattr__(self, name):
        return getattr(self.parser_module, name)


class LazyName(helpers.FakeName):
    def __init__(self, evaluator, name, value):
        super(LazyName, self).__init__(name)
        self._evaluator = evaluator
        self._value = value
        self._name = name

    @property
    @underscore_memoization
    def parent(self):
        parser_path = []
        obj = self._value
        if inspect.ismodule(obj):
            module = obj
        else:
            try:
                o = obj.__objclass__
                parser_path.append(pr.NamePart(obj.__name__, None, (None, None)))
                obj = o
            except AttributeError:
                pass

            try:
                module_name = obj.__module__
                parser_path.insert(0, pr.NamePart(obj.__name__, None, (None, None)))
            except AttributeError:
                # Unfortunately in some cases like `int` there's no __module__
                module = builtins
            else:
                module = __import__(module_name)
        raw_module = get_module(self._value)

        try:
            path = module.__file__
        except AttributeError:
            pass
        else:
            path = re.sub('c$', '', path)
            if path.endswith('.py'):
                # cut the `c` from `.pyc`
                with open(path) as f:
                    source = source_to_unicode(f.read())
                mod = FastParser(source, path[:-1]).module
                if not parser_path:
                    return mod
                found = self._evaluator.eval_call_path(iter(parser_path), mod, None)
                if found:
                    return found[0]
                debug.warning('Interpreter lookup for Python code failed %s',
                              mod)

        module = compiled.CompiledObject(raw_module)
        if raw_module == builtins:
            # The builtins module is special and always cached.
            module = compiled.builtin
        return compiled.create(self._evaluator, self._value, module, module)

    @parent.setter
    def parent(self, value):
        """Needed because of the ``representation.Simple`` super class."""


def create(evaluator, namespace, parser_module):
    ns = InterpreterNamespace(evaluator, namespace, parser_module)
    for attr_name in pr.SCOPE_CONTENTS:
        for something in getattr(parser_module, attr_name):
            something.parent = ns
