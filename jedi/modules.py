"""
Don't confuse these classes with :mod:`parsing_representation` modules, the
modules here can access these representation with ``module.parser.module``.
``Module`` exists mainly for caching purposes.

Basically :mod:`modules` offers the classes:

- ``CachedModule``, a base class for Cachedmodule.
- ``Module`` the class for all normal Python modules (not builtins, they are at
  home at :mod:`builtin`).
- ``ModuleWithCursor``, holds the module information for :class:`api.Script`.

Apart from those classes there's a ``sys.path`` fetching function, as well as
`Virtual Env` and `Django` detection.
"""
import re
import sys
import os

from jedi import cache
from jedi.common import source_to_unicode
from jedi.parser import tokenize
from jedi.parser import fast
from jedi import debug


def load_module(path=None, source=None, name=None):
    def load(source):
        if path is not None and path.endswith('.py'):
            if source is None:
                with open(path) as f:
                    source = f.read()
        else:
            # TODO refactoring remove
            from jedi.evaluate import builtin
            return builtin.BuiltinModule(path, name).parser.module
        p = path or name
        p = fast.FastParser(source_to_unicode(source), p)
        cache.save_parser(path, name, p)
        return p.module

    cached = cache.load_parser(path, name)
    return load(source) if cached is None else cached.module


class ModuleWithCursor(object):
    """
    Manages all files, that are parsed and caches them.
    Important are the params source and path, one of them has to
    be there.

    :param source: The source code of the file.
    :param path: The module path of the file or None.
    :param position: The position, the user is currently in. Only important \
    for the main file.
    """
    def __init__(self, path, source, position):
        super(ModuleWithCursor, self).__init__()
        self.path = path and os.path.abspath(path)
        self.name = None
        self.source = source
        self.position = position
        self._path_until_cursor = None
        self._line_cache = None

        # this two are only used, because there is no nonlocal in Python 2
        self._line_temp = None
        self._relevant_temp = None

    def get_path_until_cursor(self):
        """ Get the path under the cursor. """
        if self._path_until_cursor is None:  # small caching
            self._path_until_cursor, self._start_cursor_pos = \
                self._get_path_until_cursor(self.position)
        return self._path_until_cursor

    def _get_path_until_cursor(self, start_pos=None):
        def fetch_line():
            if self._is_first:
                self._is_first = False
                self._line_length = self._column_temp
                line = self._first_line
            else:
                line = self.get_line(self._line_temp)
                self._line_length = len(line)
                line = line + '\n'
            # add lines with a backslash at the end
            while True:
                self._line_temp -= 1
                last_line = self.get_line(self._line_temp)
                #print self._line_temp, repr(last_line)
                if last_line and last_line[-1] == '\\':
                    line = last_line[:-1] + ' ' + line
                    self._line_length = len(last_line)
                else:
                    break
            return line[::-1]

        self._is_first = True
        self._line_temp, self._column_temp = start_cursor = start_pos
        self._first_line = self.get_line(self._line_temp)[:self._column_temp]

        open_brackets = ['(', '[', '{']
        close_brackets = [')', ']', '}']

        gen = tokenize.generate_tokens(fetch_line)
        string = ''
        level = 0
        force_point = False
        last_type = None
        try:
            for token_type, tok, start, end, line in gen:
                # print 'tok', token_type, tok, force_point
                if last_type == token_type == tokenize.NAME:
                    string += ' '

                if level > 0:
                    if tok in close_brackets:
                        level += 1
                    if tok in open_brackets:
                        level -= 1
                elif tok == '.':
                    force_point = False
                elif force_point:
                    # it is reversed, therefore a number is getting recognized
                    # as a floating point number
                    if token_type == tokenize.NUMBER and tok[0] == '.':
                        force_point = False
                    else:
                        break
                elif tok in close_brackets:
                    level += 1
                elif token_type in [tokenize.NAME, tokenize.STRING]:
                    force_point = True
                elif token_type == tokenize.NUMBER:
                    pass
                else:
                    self._column_temp = self._line_length - end[1]
                    break

                x = start_pos[0] - end[0] + 1
                l = self.get_line(x)
                l = self._first_line if x == start_pos[0] else l
                start_cursor = x, len(l) - end[1]
                self._column_temp = self._line_length - end[1]
                string += tok
                last_type = token_type
        except tokenize.TokenError:
            debug.warning("Tokenize couldn't finish", sys.exc_info)

        # string can still contain spaces at the end
        return string[::-1].strip(), start_cursor

    def get_path_under_cursor(self):
        """
        Return the path under the cursor. If there is a rest of the path left,
        it will be added to the stuff before it.
        """
        return self.get_path_until_cursor() + self.get_path_after_cursor()

    def get_path_after_cursor(self):
        line = self.get_line(self.position[0])
        return re.search("[\w\d]*", line[self.position[1]:]).group(0)

    def get_operator_under_cursor(self):
        line = self.get_line(self.position[0])
        after = re.match("[^\w\s]+", line[self.position[1]:])
        before = re.match("[^\w\s]+", line[:self.position[1]][::-1])
        return (before.group(0) if before is not None else '') \
            + (after.group(0) if after is not None else '')

    def get_context(self, yield_positions=False):
        pos = self._start_cursor_pos
        while True:
            # remove non important white space
            line = self.get_line(pos[0])
            while True:
                if pos[1] == 0:
                    line = self.get_line(pos[0] - 1)
                    if line and line[-1] == '\\':
                        pos = pos[0] - 1, len(line) - 1
                        continue
                    else:
                        break

                if line[pos[1] - 1].isspace():
                    pos = pos[0], pos[1] - 1
                else:
                    break

            try:
                result, pos = self._get_path_until_cursor(start_pos=pos)
                if yield_positions:
                    yield pos
                else:
                    yield result
            except StopIteration:
                if yield_positions:
                    yield None
                else:
                    yield ''

    def get_line(self, line_nr):
        if not self._line_cache:
            self._line_cache = self.source.splitlines()
            if self.source:
                if self.source[-1] == '\n':
                    self._line_cache.append('')
            else:  # ''.splitlines() == []
                self._line_cache = ['']

        if line_nr == 0:
            # This is a fix for the zeroth line. We need a newline there, for
            # the backwards parser.
            return ''
        if line_nr < 0:
            raise StopIteration()
        try:
            return self._line_cache[line_nr - 1]
        except IndexError:
            raise StopIteration()

    def get_position_line(self):
        return self.get_line(self.position[0])[:self.position[1]]
