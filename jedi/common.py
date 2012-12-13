""" A universal module with functions / classes without dependencies. """
import contextlib
import tokenize

import debug
import settings


class PushBackIterator(object):
    def __init__(self, iterator):
        self.pushes = []
        self.iterator = iterator

    def push_back(self, value):
        self.pushes.append(value)

    def __iter__(self):
        return self

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.pushes:
            return self.pushes.pop()
        else:
            return next(self.iterator)


class NoErrorTokenizer(object):
    def __init__(self, readline, line_offset=0):
        self.readline = readline
        self.gen = PushBackIterator(tokenize.generate_tokens(readline))
        self.line_offset = line_offset

    def push_last_back(self):
        self.gen.push_back(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        try:
            self.current = next(self.gen)
        except tokenize.TokenError:
            # We just ignore this error, I try to handle it earlier - as
            # good as possible
            debug.warning('parentheses not closed error')
        except IndentationError:
            # This is an error, that tokenize may produce, because the code
            # is not indented as it should. Here it just ignores this line
            # and restarts the parser.
            # (This is a rather unlikely error message, for normal code,
            # tokenize seems to be pretty tolerant)
            debug.warning('indentation error on line %s, ignoring it' %
                                                        (self.start_pos[0]))
            # add the starting line of the last position
            self.line_offset += self.current[2][0]
            self.gen = PushBackIterator(tokenize.generate_tokens(
                                                                self.readline))
            self.current = self.next()
        c = list(self.current)
        c[2] += self.line_offset, 0
        return c


@contextlib.contextmanager
def scale_speed_settings(factor):
    a = settings.max_executions
    b = settings.max_until_execution_unique
    settings.max_executions *= factor
    settings.max_until_execution_unique *= factor
    yield
    settings.max_executions = a
    settings.max_until_execution_unique = b


def indent_block(text, indention='    '):
    """ This function indents a text block with a default of four spaces """
    temp = ''
    while text and text[-1] == '\n':
        temp += text[-1]
        text = text[:-1]
    lines = text.split('\n')
    return '\n'.join(map(lambda s: indention + s, lines)) + temp
