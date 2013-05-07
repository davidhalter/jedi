""" A universal module with functions / classes without dependencies. """
import sys
import contextlib
import functools
import tokenizer as tokenize

from jedi._compatibility import next, reraise
from jedi import settings

FLOWS = ['if', 'else', 'elif', 'while', 'with', 'try', 'except', 'finally']


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
        self.current = None

    def push_back(self, value):
        self.pushes.append(value)

    def __iter__(self):
        return self

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.pushes:
            self.current = self.pushes.pop()
        else:
            self.current = next(self.iterator)
        return self.current


class NoErrorTokenizer(object):
    def __init__(self, readline, offset=(0, 0), is_fast_parser=False):
        self.readline = readline
        self.gen = tokenize.generate_tokens(readline)
        self.offset = offset
        self.closed = False
        self.is_first = True
        self.push_backs = []

        # fast parser options
        self.is_fast_parser = is_fast_parser
        self.current = self.previous = [None, None, (0, 0), (0, 0), '']
        self.in_flow = False
        self.new_indent = False
        self.parser_indent = self.old_parser_indent = 0
        self.is_decorator = False
        self.first_stmt = True

    def push_last_back(self):
        self.push_backs.append(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.closed:
            raise MultiLevelStopIteration()
        if self.push_backs:
            return self.push_backs.pop(0)

        self.last_previous = self.previous
        self.previous = self.current
        self.current = next(self.gen)
        c = list(self.current)

        if c[0] == tokenize.ENDMARKER:
            self.current = self.previous
            self.previous = self.last_previous
            raise MultiLevelStopIteration()

        # this is exactly the same check as in fast_parser, but this time with
        # tokenize and therefore precise.
        breaks = ['def', 'class', '@']

        if self.is_first:
            c[2] = self.offset[0] + c[2][0], self.offset[1] + c[2][1]
            c[3] = self.offset[0] + c[3][0], self.offset[1] + c[3][1]
            self.is_first = False
        else:
            c[2] = self.offset[0] + c[2][0], c[2][1]
            c[3] = self.offset[0] + c[3][0], c[3][1]
        self.current = c

        def close():
            if not self.first_stmt:
                self.closed = True
                raise MultiLevelStopIteration()
        # ignore indents/comments
        if self.is_fast_parser \
                and self.previous[0] in (tokenize.INDENT, tokenize.NL, None,
                                         tokenize.NEWLINE, tokenize.DEDENT) \
                and c[0] not in (tokenize.COMMENT, tokenize.INDENT,
                             tokenize.NL, tokenize.NEWLINE, tokenize.DEDENT):
            #print c, tokenize.tok_name[c[0]]

            tok = c[1]
            indent = c[2][1]
            if indent < self.parser_indent:  # -> dedent
                self.parser_indent = indent
                self.new_indent = False
                if not self.in_flow or indent < self.old_parser_indent:
                    close()
                self.in_flow = False
            elif self.new_indent:
                self.parser_indent = indent
                self.new_indent = False

            if not self.in_flow:
                if tok in FLOWS or tok in breaks:
                    self.in_flow = tok in FLOWS
                    if not self.is_decorator and not self.in_flow:
                        close()
                    self.is_decorator = '@' == tok
                    if not self.is_decorator:
                        self.old_parser_indent = self.parser_indent
                        self.parser_indent += 1  # new scope: must be higher
                        self.new_indent = True

            if tok != '@':
                if self.first_stmt and not self.new_indent:
                    self.parser_indent = indent
                self.first_stmt = False
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


@contextlib.contextmanager
def ignored(*exceptions):
    """Context manager that ignores all of the specified exceptions. This will
    be in the standard library starting with Python 3.4."""
    try:
        yield
    except exceptions:
        pass
