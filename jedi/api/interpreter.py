from jedi.evaluate import compiled
from jedi.parser import representation as pr
from jedi.evaluate import helpers


class InterpreterNamespace(pr.Module):
    def __init__(self, namespace, parser_module):
        self.namespace = namespace
        self.parser_module = parser_module

    def get_defined_names(self):
        for key, value in self.namespace.items():
            yield LazyName(key, value)

    def __getattr__(self, name):
        return getattr(self.parser_module, name)


class LazyName(helpers.FakeName):
    def __init__(self, name, parent_obj):
        super(LazyName, self).__init__(name)
        self._parent_obj = parent_obj

    @property
    def parent(self):
        return compiled.create(self._parent_obj)

    @parent.setter
    def parent(self, value):
        """Needed because of the ``representation.Simple`` super class."""


def create(namespace, parser_module):
    ns = InterpreterNamespace(namespace, parser_module)
    parser_module.statements[0].parent = ns
