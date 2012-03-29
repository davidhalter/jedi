import imp
import sys

import debug
import parsing

files = {}
load_module_cb = None
module_find_path = sys.path[1:]


class ModuleNotFound(Exception):
    pass


class File(object):
    """
    Manages all files, that are parsed and caches them.

    :param source: The source code of the file.
    :param module_name: The module name of the file.
    """
    def __init__(self, module_name, source):
        self.source = source
        self.module_name = module_name
        self._line_cache = None
        self._parser = None

    @property
    def parser(self):
        if self._parser:
            return self._parser
        if not self.module_name and not self.source:
            raise AttributeError("Submit a module name or the source code")
        elif self.module_name:
            return self.load_module()

    def load_module(self):
        self._parser = parsing.PyFuzzyParser(self.source)
        return self._parser

    def get_line(self, line):
        if not self._line_cache:
            self._line_cache = self.source.split('\n')

        if 1 <= line <= len(self._line_cache):
            return self._line_cache[line - 1]
        else:
            return None

class BuiltinModule:
    def __init__(self, name):
        self.name = name
        self.content = {}
        exec 'import %s as module' % name in self.content
        self.module = self.content['module']

    @property
    def docstr(self):
        # TODO get the help string, not just the docstr
        return self.module.__doc__

    def get_defined_names(self):
        return dir(self.module)

def find_module(point_path):
    """
    Find a module with a path (of the module, like usb.backend.libusb10).

    :param point_path: A name from the parser.
    :return: The rest of the path, and the module top scope.
    """
    def follow_str(ns, string):
        debug.dbg('follow_module', ns, string)
        if ns:
            path = ns[1]
        else:
            # TODO modules can be system modules, without '.' in path
            path = module_find_path
            debug.dbg('search_module', string, path)
        try:
            i = imp.find_module(string, path)
        except ImportError:
            # find builtins (ommit path):
            i = imp.find_module(string)
            if i[0]:
                # if the import has a file descriptor, it cannot be a builtin.
                raise
        return i

    # now execute those paths
    current_namespace = None
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

    if current_namespace[0]:
        f = File(current_namespace[2], current_namespace[0].read())
        scope = f.parser.top
    else:
        scope = BuiltinModule(current_namespace[1])
    return scope, rest
