"""
Module for statical analysis.
"""

from jedi import debug


CODES = {
    'attribute-error': (1, 'Potential AttributeError.'),
}


class Error(object):
    def __init__(self, name, module_path, start_pos):
        self._module_path = module_path
        self._start_pos = start_pos
        self.name = name

    @property
    def line(self):
        return self._start_pos[0]

    @property
    def column(self):
        return self._start_pos[1]

    @property
    def code(self):
        # The class name start
        first = self.__class__.__name__[0]
        return first + str(CODES[self.name][0])

    def __str__(self):
        return '%s: %s' % (self.code, self.line)

    def __repr__(self):
        return '<%s %s: %s@%s,%s' % (self.__class__.__name__,
                                     self.name, self._module_path,
                                     self._start_pos[0], self._start_pos[1])


class Warning(Error):
    pass


def add(evaluator, name, jedi_obj, typ=Error):
    module_path = jedi_obj.get_parent_until().path
    instance = typ(name, module_path, jedi_obj.start_pos)
    debug.warning(str(instance))
    evaluator.analysis.append(instance)
