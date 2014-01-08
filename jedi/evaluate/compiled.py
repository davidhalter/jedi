"""
Imitate the parser representation.
"""
import inspect

from jedi._compatibility import builtins
from jedi.cache import underscore_memoization


class PyObject(object):
    def __init__(self, obj, parent=None, instantiated=False):
        self.obj = obj
        self.parent = parent
        self.instantiated = instantiated

    def get_defined_names(self):
        for name in dir(self.obj):
            yield PyName(self, name)

    def isinstance(self, *obj):
        return isinstance(self, obj)

    @property
    def name(self):
        # might not exist sometimes (raises AttributeError)
        return self.obj.__name__

    def execute(self, params):
        if inspect.isclass(self.obj):
            return [PyObject(self.obj, self.parent, True)]
        elif inspect.isbuiltin(self.obj) or inspect.ismethod(self.obj) \
                or inspect.ismethoddescriptor(self.obj):
            return []
        else:
            return []
        return []


class PyName(object):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name

        self.start_pos = 0, 0  # an illegal start_pos, to make sorting easy.

    @property
    @underscore_memoization
    def parent(self):
        try:
            # this has a builtin_function_or_method
            o = getattr(self._obj.obj, self._name)
        except AttributeError:
            # happens e.g. in properties of
            # PyQt4.QtGui.QStyleOptionComboBox.currentText
            # -> just set it to None
            return PyObject(obj, py_builtin)
        return PyObject(o, self._obj)

    def get_code(self):
        return self._name

py_builtin = PyObject(builtins)
