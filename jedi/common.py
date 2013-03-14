""" A universal module with functions / classes without dependencies. """
import sys
import contextlib
import functools
import tokenize

from jedi._compatibility import next, reraise
from jedi import debug
from jedi import settings


class MultiLevelStopIteration(Exception):
    """
    StopIteration's get catched pretty easy by for loops, let errors propagate.
    """
    pass


class UncaughtAttributeError(Exception):
    """
    Important, because `__getattr__` and `hasattr` catch AttributeErrors
    implicitly. This is really evil (mainly because of `__getattr__`).
    `hasattr` in Python 2 is even more evil, because it catches ALL exceptions.
    Therefore this class originally had to be derived from `BaseException`
    instead of `Exception`.  But because I removed relevant `hasattr` from
    the code base, we can now switch back to `Exception`.

    :param base: return values of sys.exc_info().
    """


def rethrow_uncaught(func):
    """
    Re-throw uncaught `AttributeError`.

    Usage:  Put ``@rethrow_uncaught`` in front of the function
    which does **not** suppose to raise `AttributeError`.

    AttributeError is easily get caught by `hasattr` and another
    ``except AttributeError`` clause.  This becomes problem when you use
    a lot of "dynamic" attributes (e.g., using ``@property``) because you
    can't distinguish if the property does not exist for real or some code
    inside of the "dynamic" attribute through that error.  In a well
    written code, such error should not exist but getting there is very
    difficult.  This decorator is to help us getting there by changing
    `AttributeError` to `UncaughtAttributeError` to avoid unexpected catch.
    This helps us noticing bugs earlier and facilitates debugging.

    .. note:: Treating StopIteration here is easy.
              Add that feature when needed.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        try:
            return func(*args, **kwds)
        except AttributeError:
            exc_info = sys.exc_info()
            reraise(UncaughtAttributeError(exc_info[1]), exc_info[2])
    return wrapper


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
    def __init__(self, readline, offset=(0, 0), stop_on_scope=False):
        self.readline = readline
        self.gen = PushBackIterator(tokenize.generate_tokens(readline))
        self.offset = offset
        self.stop_on_scope = stop_on_scope
        self.first_scope = False
        self.closed = False
        self.first = True

    def push_last_back(self):
        self.gen.push_back(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.closed:
            raise MultiLevelStopIteration()
        try:
            self.current = next(self.gen)
        except tokenize.TokenError:
            # We just ignore this error, I try to handle it earlier - as
            # good as possible
            debug.warning('parentheses not closed error')
            return self.__next__()
        except IndentationError:
            # This is an error, that tokenize may produce, because the code
            # is not indented as it should. Here it just ignores this line
            # and restarts the parser.
            # (This is a rather unlikely error message, for normal code,
            # tokenize seems to be pretty tolerant)
            debug.warning('indentation error on line %s, ignoring it' %
                                                        self.current[2][0])
            # add the starting line of the last position
            self.offset = (self.offset[0] + self.current[2][0],
                           self.current[2][1])
            self.gen = PushBackIterator(tokenize.generate_tokens(
                                                                self.readline))
            return self.__next__()

        c = list(self.current)

        # stop if a new class or definition is started at position zero.
        breaks = ['def', 'class', '@']
        if self.stop_on_scope and c[1] in breaks and c[2][1] == 0:
            if self.first_scope:
                self.closed = True
                raise MultiLevelStopIteration()
            elif c[1] != '@':
                self.first_scope = True

        if self.first:
            c[2] = self.offset[0] + c[2][0], self.offset[1] + c[2][1]
            c[3] = self.offset[0] + c[3][0], self.offset[1] + c[3][1]
            self.first = False
        else:
            c[2] = self.offset[0] + c[2][0], c[2][1]
            c[3] = self.offset[0] + c[3][0], c[3][1]
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
