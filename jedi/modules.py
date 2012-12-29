from __future__ import with_statement

from _compatibility import exec_function, unicode

import re
import tokenize
import sys
import os
import time

import cache
import parsing
import fast_parser
import builtin
import debug
import settings


class Module(builtin.CachedModule):
    """
    Manages all files, that are parsed and caches them.

    :param path: The module path of the file.
    :param source: The source code of the file.
    """
    def __init__(self, path, source=None):
        super(Module, self).__init__(path=path)
        if source is None:
            with open(path) as f:
                source = f.read()
        self.source = source_to_unicode(source)
        self._line_cache = None

    def _get_source(self):
        """ Just one time """
        s = self.source
        del self.source  # memory efficiency
        return s


class ModuleWithCursor(Module):
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
        super(ModuleWithCursor, self).__init__(path, source)
        self.position = position

        # this two are only used, because there is no nonlocal in Python 2
        self._line_temp = None
        self._relevant_temp = None

        self.source = source
        self._part_parser = None

    @property
    def parser(self):
        """ get the parser lazy """
        if not self._parser:
            try:
                ts, parser = builtin.CachedModule.cache[self.path]
                cache.invalidate_star_import_cache(parser.module)

                del builtin.CachedModule.cache[self.path]
            except KeyError:
                pass
            # Call the parser already here, because it will be used anyways.
            # Also, the position is here important (which will not be used by
            # default), therefore fill the cache here.
            self._parser = fast_parser.FastParser(self.source, self.path,
                                                        self.position)
            if self.path is not None:
                builtin.CachedModule.cache[self.path] = time.time(), \
                                                        self._parser
        return self._parser

    def get_path_until_cursor(self):
        """ Get the path under the cursor. """
        result = self._get_path_until_cursor()
        self._start_cursor_pos = self._line_temp + 1, self._column_temp
        return result

    def _get_path_until_cursor(self, start_pos=None):
        def fetch_line():
            line = self.get_line(self._line_temp)
            if self._is_first:
                self._is_first = False
                self._line_length = self._column_temp
                line = line[:self._column_temp]
            else:
                self._line_length = len(line)
                line = line + '\n'
            # add lines with a backslash at the end
            while 1:
                self._line_temp -= 1
                last_line = self.get_line(self._line_temp)
                if last_line and last_line[-1] == '\\':
                    line = last_line[:-1] + ' ' + line
                else:
                    break
            return line[::-1]

        self._is_first = True
        if start_pos is None:
            self._line_temp = self.position[0]
            self._column_temp = self.position[1]
        else:
            self._line_temp, self._column_temp = start_pos

        open_brackets = ['(', '[', '{']
        close_brackets = [')', ']', '}']

        gen = tokenize.generate_tokens(fetch_line)
        string = ''
        level = 0
        force_point = False
        last_type = None
        try:
            for token_type, tok, start, end, line in gen:
                #print 'tok', token_type, tok, force_point
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
                    break

                self._column_temp = self._line_length - end[1]
                string += tok
                last_type = token_type
        except tokenize.TokenError:
            debug.warning("Tokenize couldn't finish", sys.exc_info)

        # string can still contain spaces at the end
        return string[::-1].strip()

    def get_path_under_cursor(self):
        """
        Return the path under the cursor. If there is a rest of the path left,
        it will be added to the stuff before it.
        """
        line = self.get_line(self.position[0])
        after = re.search("[\w\d]*", line[self.position[1]:]).group(0)
        return self.get_path_until_cursor() + after

    def get_operator_under_cursor(self):
        line = self.get_line(self.position[0])
        after = re.match("[^\w\s]+", line[self.position[1]:])
        before = re.match("[^\w\s]+", line[:self.position[1]][::-1])
        return (before.group(0) if before is not None else '') \
                + (after.group(0) if after is not None else '')

    def get_context(self):
        pos = self._start_cursor_pos
        while pos > (1, 0):
            # remove non important white space
            line = self.get_line(pos[0])
            while pos[1] > 0 and line[pos[1] - 1].isspace():
                pos = pos[0], pos[1] - 1

            try:
                yield self._get_path_until_cursor(start_pos=pos)
            except StopIteration:
                yield ''
            pos = self._line_temp, self._column_temp

        while True:
            yield ''

    def get_line(self, line_nr):
        if not self._line_cache:
            self._line_cache = self.source.split('\n')

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

    def get_part_parser(self):
        """ Returns a parser that contains only part of the source code. This
        exists only because of performance reasons.
        """
        if self._part_parser:
            return self._part_parser

        # TODO check for docstrings
        length = settings.part_line_length
        offset = max(self.position[0] - length, 0)
        s = '\n'.join(self.source.split('\n')[offset:offset + length])
        self._part_parser = parsing.PyFuzzyParser(s, self.path, self.position,
                                                        line_offset=offset)
        return self._part_parser


@cache.memoize_default([])
def sys_path_with_modifications(module):
    def execute_code(code):
        c = "import os; from os.path import *; result=%s"
        variables = {'__file__': module.path}
        try:
            exec_function(c % code, variables)
        except Exception:
            debug.warning('sys path detected, but failed to evaluate')
            return None
        try:
            res = variables['result']
            if isinstance(res, str):
                return os.path.abspath(res)
            else:
                return None
        except KeyError:
            return None

    def check_module(module):
        try:
            possible_stmts = module.used_names['path']
        except KeyError:
            return builtin.get_sys_path()

        sys_path = list(builtin.get_sys_path())  # copy
        for p in possible_stmts:
            try:
                call = p.get_assignment_calls().get_only_subelement()
            except AttributeError:
                continue
            n = call.name
            if not isinstance(n, parsing.Name) or len(n.names) != 3:
                continue
            if n.names[:2] != ('sys', 'path'):
                continue
            array_cmd = n.names[2]
            if call.execution is None:
                continue
            exe = call.execution
            if not (array_cmd == 'insert' and len(exe) == 2
                    or array_cmd == 'append' and len(exe) == 1):
                continue

            if array_cmd == 'insert':
                exe_type, exe.type = exe.type, parsing.Array.NOARRAY
                exe_pop = exe.values.pop(0)
                res = execute_code(exe.get_code())
                if res is not None:
                    sys_path.insert(0, res)
                    debug.dbg('sys path inserted: %s' % res)
                exe.type = exe_type
                exe.values.insert(0, exe_pop)
            elif array_cmd == 'append':
                res = execute_code(exe.get_code())
                if res is not None:
                    sys_path.append(res)
                    debug.dbg('sys path added: %s' % res)
        return sys_path

    if module.path is None:
        return []  # support for modules without a path is intentionally bad.

    curdir = os.path.abspath(os.curdir)
    try:
        os.chdir(os.path.dirname(module.path))
    except OSError:
        pass

    result = check_module(module)
    result += detect_django_path(module.path)

    # cleanup, back to old directory
    os.chdir(curdir)
    return result


def detect_django_path(module_path):
    """ Detects the path of the very well known Django library (if used) """
    result = []
    while True:
        new = os.path.dirname(module_path)
        # If the module_path doesn't change anymore, we're finished -> /
        if new == module_path:
            break
        else:
            module_path = new

        try:
            with open(module_path + os.path.sep + 'manage.py'):
                debug.dbg('Found django path: %s' % module_path)
                result.append(module_path)
        except IOError:
            pass
    return result


def source_to_unicode(source, encoding=None):
    def detect_encoding():
        """ For the implementation of encoding definitions in Python, look at:
        http://www.python.org/dev/peps/pep-0263/
        http://docs.python.org/2/reference/lexical_analysis.html#encoding-\
                                                                declarations
        """
        if encoding is not None:
            return encoding

        if source.startswith('\xef\xbb\xbf'):
            # UTF-8 byte-order mark
            return 'utf-8'

        first_two_lines = re.match(r'(?:[^\n]*\n){0,2}', source).group(0)
        possible_encoding = re.match("coding[=:]\s*([-\w.]+)", first_two_lines)
        if possible_encoding:
            return possible_encoding.group(1)
        else:
            # the default if nothing else has been set -> PEP 263
            return 'iso-8859-1'

    if isinstance(source, unicode):
        # only cast str/bytes
        return source

    # cast to unicode by default
    return unicode(source, detect_encoding(), 'replace')
