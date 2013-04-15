""" A universal module with functions / classes without dependencies. """
import contextlib
import tokenize

from _compatibility import next
import debug
import settings

FLOWS = ['if', 'else', 'elif', 'while', 'with', 'try', 'except', 'finally']


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
    def __init__(self, readline, offset=(0, 0), is_fast_parser=False):
        self.readline = readline
        self.gen = PushBackIterator(tokenize.generate_tokens(readline))
        self.offset = offset
        self.closed = False
        self.is_first = True

        # fast parser options
        self.is_fast_parser = is_fast_parser
        self.current = self.previous = [None, None, (0, 0), (0, 0), '']
        self.in_flow = False
        self.new_indent = False
        self.parser_indent = 0
        self.is_decorator = False
        self.first_stmt = True

    def push_last_back(self):
        self.gen.push_back(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.closed:
            raise MultiLevelStopIteration()
        try:
            self.last_previous = self.previous
            self.previous = self.current
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
                if not self.in_flow:
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
