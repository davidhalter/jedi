from __future__ import with_statement
import re
import tokenize
import imp
import os

import debug
import parsing
import builtin

files = {}
load_module_cb = None


class ModuleNotFound(Exception):
    pass


class Module(builtin.CachedModule):
    """
    Manages all files, that are parsed and caches them.

    :param source: The source code of the file.
    :param path: The module path of the file.
    """
    module_cache = {}

    def __init__(self, path, source):
        super(Module, self).__init__(path=path)
        self.source = source
        self._line_cache = None

    def _get_source(self):
        return self.source

    def _load_module(self):
        self._parser = parsing.PyFuzzyParser(self.source, self.path)
        del self.source  # efficiency

        # insert into cache
        to_cache = (os.path.getmtime(self.path), self._parser)
        Module.module_cache[self.path] = to_cache


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
            while self._line_temp > 1:
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

        try:
            return self._line_cache[line - 1]
        except IndexError:
            raise StopIteration()


def find_module(current_module, point_path):
    """
    Find a module with a path (of the module, like usb.backend.libusb10).

    Relative imports: http://www.python.org/dev/peps/pep-0328
    are only used like this (py3000): from .module import name.

    :param current_ns_path: A path to the current namespace.
    :param point_path: A name from the parser.
    :return: The rest of the path, and the module top scope.
    """
    def follow_str(ns, string):
        debug.dbg('follow_module', ns, string)
        if ns:
            path = [ns[1]]
        else:
            path = None
            debug.dbg('search_module', string, path,
                                            current_module.path)
        try:
            i = imp.find_module(string, path)
        except ImportError:
            # find builtins (ommit path):
            i = imp.find_module(string, builtin.module_find_path)
        return i

    # TODO handle relative paths - they are included in the import object
    current_namespace = None
    builtin.module_find_path.insert(0, os.path.dirname(current_module.path))
    # now execute those paths
    rest = []
    for i, s in enumerate(point_path):
        try:
            current_namespace = follow_str(current_namespace, s)
        except ImportError:
            if current_namespace:
                rest = point_path[i:]
            else:
                raise ModuleNotFound(
                        'The module you searched has not been found')

    builtin.module_find_path.pop(0)
    path = current_namespace[1]
    is_package_directory = current_namespace[2][2] == imp.PKG_DIRECTORY

    f = None
    if is_package_directory or current_namespace[0]:
        # is a directory module
        if is_package_directory:
            path += '/__init__.py'
            with open(path) as f:
                source = f.read()
        else:
            source = current_namespace[0].read()
        if path.endswith('.py'):
            f = Module(path, source)
        else:
            f = builtin.Parser(path=path)
    else:
        f = builtin.Parser(name=path)

    return f.parser.top, rest
