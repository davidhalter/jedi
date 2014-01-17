import re
import os
import sys

from jedi import cache
from jedi.parser import tokenize
from jedi.parser.fast import FastParser
from jedi.parser import representation
from jedi import debug


class UserContext(object):
    """
    :param source: The source code of the file.
    :param position: The position, the user is currently in. Only important \
    for the main file.
    """
    def __init__(self, source, position):
        self.source = source
        self.position = position
        self._line_cache = None

        # this two are only used, because there is no nonlocal in Python 2
        self._line_temp = None
        self._relevant_temp = None

    @cache.underscore_memoization
    def get_path_until_cursor(self):
        """ Get the path under the cursor. """
        path, self._start_cursor_pos = self._calc_path_until_cursor(self.position)
        return path

    def _calc_path_until_cursor(self, start_pos=None):
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
            debug.warning("Tokenize couldn't finish: %s", sys.exc_info)

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
                result, pos = self._calc_path_until_cursor(start_pos=pos)
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


class UserContextParser(object):
    def __init__(self, source, path, position, user_context):
        self._source = source
        self._path = path and os.path.abspath(path)
        self._position = position
        self._user_context = user_context

    @cache.underscore_memoization
    def _parser(self):
        cache.invalidate_star_import_cache(self._path)
        parser = FastParser(self._source, self._path)
        # Don't pickle that module, because the main module is changing quickly
        cache.save_parser(self._path, None, parser, pickling=False)
        return parser

    @cache.underscore_memoization
    def _get_user_stmt(self):
        return self.module().get_statement_for_position(self._position,
                                                        include_imports=True)

    def user_stmt(self, is_completion=False):
        user_stmt = self._get_user_stmt()

        debug.speed('parsed')

        if is_completion and not user_stmt:
            # for statements like `from x import ` (cursor not in statement)
            pos = next(self._user_context.get_context(yield_positions=True))
            last_stmt = pos and \
                self.module().get_statement_for_position(pos, include_imports=True)
            if isinstance(last_stmt, representation.Import):
                user_stmt = last_stmt
        return user_stmt

    @cache.underscore_memoization
    def user_scope(self):
        user_stmt = self._get_user_stmt()
        if user_stmt is None:
            def scan(scope):
                for s in scope.statements + scope.subscopes:
                    if isinstance(s, representation.Scope):
                        if s.start_pos <= self._position <= s.end_pos:
                            return scan(s) or s

            return scan(self.module()) or self.module()
        else:
            return user_stmt.parent

    def module(self):
        return self._parser().module
