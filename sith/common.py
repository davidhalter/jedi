""" A universal module with functions / classes without dependencies. """
import contextlib
import tokenize

from _compatibility import next
import debug
import settings


class MultiLevelStopIteration(Exception):
    """
    StopIteration's get catched pretty easy by for loops, let errors propagate.
    """
    pass


class MultiLevelAttributeError(Exception):
    """
    Important, because `__getattr__` and `hasattr` catch AttributeErrors
    implicitly. This is really evil (mainly because of `__getattr__`).
    `hasattr` in Python 2 is even more evil, because it catches ALL exceptions.
    Therefore this class has to be a `BaseException` and not an `Exception`.
    But because I rewrote hasattr, we can now switch back to `Exception`.

    :param base: return values of sys.exc_info().
    """
    def __init__(self, base=None):
        self.base = base

    def __str__(self):
        import traceback
        tb = traceback.format_exception(*self.base)
        return 'Original:\n\n' + ''.join(tb)


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
    def __init__(self, readline, line_offset=0, stop_on_scope=False):
        self.readline = readline
        self.gen = PushBackIterator(tokenize.generate_tokens(readline))
        self.line_offset = line_offset
        self.stop_on_scope = stop_on_scope
        self.first_scope = False
        self.closed = False

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
            self.line_offset += self.current[2][0]
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

        c[2] = self.line_offset + c[2][0], c[2][1]
        c[3] = self.line_offset + c[3][0], c[3][1]
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
