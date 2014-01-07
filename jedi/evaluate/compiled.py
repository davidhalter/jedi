from jedi.cache import underscore_memoization


class PyObject(object):
    def __init__(self, obj, parent=None):
        self.obj = obj
        self.parent = parent

    def get_defined_names(self):
        for name in dir(self.obj):
            yield PyName(self, name)


class PyName(object):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name

        self.start_pos = 0, 0  # an illegal start_pos, to make sorting easy.

    @property
    @underscore_memoization
    def parent(self):
        return PyObject(getattr(self._obj.obj, self._name), self._obj)
