from __future__ import with_statement
import re
import tokenize
import sys

import parsing
import builtin
import debug

files = {}
load_module_cb = None


class Module(builtin.CachedModule):
    """
    Manages all files, that are parsed and caches them.

    :param source: The source code of the file.
    :param path: The module path of the file.
    """
    def __init__(self, path, source):
        super(Module, self).__init__(path=path)
        self.source = source
        self._line_cache = None

    def _get_source(self):
        s = self.source
        del self.source  # memory efficiency
        return s


class ModuleWithCursor(Module):
    """
    Manages all files, that are parsed and caches them.
    Important are the params source and path, one of them has to
    be there.

    :param source: The source code of the file.
    :param path: The module path of the file.
    :param position: The position, the user is currently in. Only important \
    for the main file.
    """
    def __init__(self, path, source, position):
        super(ModuleWithCursor, self).__init__(path, source)
        self.position = position

        # this two are only used, because there is no nonlocal in Python 2
        self._line_temp = None
        self._relevant_temp = None

        # Call the parser already here, because it will be used anyways.
        # Also, the position is here important (which will not be used by
        # default), therefore fill the cache here.
        self._parser = parsing.PyFuzzyParser(source, path, position)

    def get_path_until_cursor(self):
        """ Get the path under the cursor. """
        self._is_first = True

        def fetch_line():
            line = self.get_line(self._line_temp)
            if self._is_first:
                self._is_first = False
                line = line[:self.position[1]]
            else:
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

        self._line_temp = self.position[0]

        force_point = False
        open_brackets = ['(', '[', '{']
        close_brackets = [')', ']', '}']

        gen = tokenize.generate_tokens(fetch_line)
        string = ''
        level = 0
        try:
            for token_type, tok, start, end, line in gen:
                #print token_type, tok, force_point
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
                        #print 'break2', token_type, tok
                        break
                elif tok in close_brackets:
                    level += 1
                elif token_type in [tokenize.NAME, tokenize.STRING]:
                    force_point = True
                elif token_type == tokenize.NUMBER:
                    pass
                else:
                    #print 'break', token_type, tok
                    break

                string += tok
        except tokenize.TokenError:
            debug.warning("Tokenize couldn't finish", sys.exc_info)

        return string[::-1]

    def get_path_under_cursor(self):
        """
        Return the path under the cursor. If there is a rest of the path left,
        it will be added to the stuff before it.
        """
        line = self.get_line(self.position[0])
        after = re.search("[\w\d]*", line[self.position[1]:]).group(0)
        return self.get_path_until_cursor() + after

    def get_line(self, line):
        if not self._line_cache:
            self._line_cache = self.source.split('\n')

        if line < 1:
            raise StopIteration()
        try:
            return self._line_cache[line - 1]
        except IndexError:
            raise StopIteration()
