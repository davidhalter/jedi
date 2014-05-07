"""
Module for statical analysis.
"""

from jedi import debug


CODES = {
    'inaccesible': (1, 'Attribute is not accessible.'),
}


class Error(object):
    def __init__(self, name, start_pos):
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


class Warning(Error):
    pass


def add(evaluator, code, typ=Error):
    instance = typ()
    debug.warning(str(Error))
    evaluator.analysis.append(instance)
