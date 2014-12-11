import inspect
import re

from jedi._compatibility import builtins
from jedi import debug
from jedi.common import source_to_unicode
from jedi.cache import underscore_memoization
from jedi.evaluate import compiled
from jedi.evaluate.compiled.fake import get_module
from jedi.parser import tree as pt
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser
from jedi.evaluate import helpers
from jedi.evaluate import iterable


class InterpreterNamespace(pt.Module):
    def __init__(self, evaluator, namespace, parser_module):
        self.namespace = namespace
        self.parser_module = parser_module
        self._evaluator = evaluator

        for key, value in self.namespace.items():
            arr = self.parser_module.names_dict.setdefault(key, [])
            arr.append(LazyName(self._evaluator, parser_module, key, value))

    @underscore_memoization
    def get_defined_names(self):
        raise NotImplementedError
        for name in self.parser_module.get_defined_names():
            yield name
        for key, value in self.namespace.items():
            yield LazyName(self._evaluator, key, value)

    @underscore_memoization
    def used_names(self):
        raise NotImplementedError
        for name in self.parser_module.get_defined_names():
            yield name
        for key, value in self.namespace.items():
            yield LazyName(self._evaluator, key, value)

    def scope_names_generator(self, position=None):
        raise NotImplementedError
        yield self, list(self.get_defined_names())

    def __getattr__(self, name):
        return getattr(self.parser_module, name)


class LazyName(helpers.FakeName):
    def __init__(self, evaluator, module, name, value):
        super(LazyName, self).__init__(name)
        self._module = module
        self._evaluator = evaluator
        self._value = value
        self._name = name

    def is_definition(self):
        return True

    @property
    @underscore_memoization
    def parent(self):
        obj = self._value
        parser_path = []
        if inspect.ismodule(obj):
            module = obj
        else:
            class FakeParent(pt.Base):
                parent = compiled.builtin

            names = []
            try:
                o = obj.__objclass__
                names.append(obj.__name__)
                obj = o
            except AttributeError:
                pass

            try:
                module_name = obj.__module__
                names.insert(0, obj.__name__)
            except AttributeError:
                # Unfortunately in some cases like `int` there's no __module__
                module = builtins
            else:
                module = __import__(module_name)
            parser_path = [helpers.FakeName(n, FakeParent()) for n in names]
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
                mod = FastParser(load_grammar(), source, path[:-1]).module
                if not parser_path:
                    return mod
                assert len(parser_path) == 1
                found = self._evaluator.find_types(mod, parser_path[0], search_global=True)
                #found = self._evaluator.eval_call_path(iter(parser_path), mod, None)
                if found:
                    content = iterable.AlreadyEvaluated(found)
                    s = pt.ExprStmt([self, pt.Operator('=', (0, 0), ''), content])
                    s.parent = self._module
                    return s
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
    #for attr_name in pt.SCOPE_CONTENTS:
    #    for something in getattr(parser_module, attr_name):
    #        something.parent = ns
