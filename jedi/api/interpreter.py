"""
TODO Some parts of this module are still not well documented.
"""
import inspect
import re
import sys

from jedi._compatibility import builtins
from jedi import debug
from jedi.common import source_to_unicode
from jedi.cache import underscore_memoization
from jedi.evaluate import compiled
from jedi.parser import tree as pt
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser
from jedi.evaluate import helpers
from jedi.evaluate import iterable
from jedi.evaluate.compiled import mixed


def add_namespaces_to_parser(evaluator, namespaces, parser_module):
    for namespace in namespaces:
        for key, value in namespace.items():
            # Name lookups in an ast tree work by checking names_dict.
            # Therefore we just add fake names to that and we're done.
            arr = parser_module.names_dict.setdefault(key, [])
            arr.append(LazyName(evaluator, parser_module, key, value))


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
        """
        Creating fake statements for the interpreter.

        Here we are trying to link back to Python code, if possible. This means
        we try to find the python module for a name (not the builtin).
        """
        return mixed.create(self._evaluator, self._value)
        obj = self._value
        parser_path = []
        if inspect.ismodule(obj):
            module = obj
        else:
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
                # If we put anything into fromlist, it will just return the
                # latest name.
                module = __import__(module_name, fromlist=[''])
            parser_path = names

        found = []
        try:
            path = module.__file__
        except AttributeError:
            pass
        else:
            # Find the corresponding Python file for an interpreted one.
            path = re.sub(r'\.pyc$', '.py', path)

            if path.endswith('.py'):
                with open(path) as f:
                    source = source_to_unicode(f.read())
                mod = FastParser(load_grammar(), source, path).module
                mod = self._evaluator.wrap(mod)

                # We have to make sure that the modules that we import are also
                # part of evaluator.modules.
                for module_name, module in sys.modules.items():
                    try:
                        iterated_path = module.__file__
                    except AttributeError:
                        pass
                    else:
                        if iterated_path == path:
                            self._evaluator.modules[module_name] = mod
                            break
                else:
                    raise NotImplementedError('This should not happen, a module '
                                              'should be part of sys.modules.')

                if parser_path:
                    #assert len(parser_path) == 1
                    found = list(self._evaluator.find_types(mod, parser_path[0],
                                                            search_global=True))
                else:
                    found = [mod]

                if not found:
                    debug.warning('Interpreter lookup failed in global scope for %s',
                                  parser_path)

        if not found:
            evaluated = compiled.create(self._evaluator, obj)
            found = [evaluated]

        if len(found) > 1:
            content = iterable.AlreadyEvaluated(found)
            stmt = pt.ExprStmt([self, pt.Operator(pt.zero_position_modifier,
                                                  '=', (0, 0), ''), content])
            stmt.parent = self._module
            return stmt
        else:
            return found[0]

    @parent.setter
    def parent(self, value):
        """Needed because the super class tries to set parent."""
