import imp
import sys
import os

import debug
import parsing
import builtin

files = {}
load_module_cb = None
module_find_path = sys.path[1:]


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
            i = imp.find_module(string, module_find_path)
        return i

    # TODO handle relative paths - they are included in the import object
    current_namespace = None
    module_find_path.insert(0, os.path.dirname(current_module.path))
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

    module_find_path.pop(0)
    path = current_namespace[1]
    is_package_directory = current_namespace[2][2] == imp.PKG_DIRECTORY

    f = None
    if is_package_directory or current_namespace[0]:
        # is a directory module
        if is_package_directory:
            path += '/__init__.py'
            # python2.5 cannot cope with the `with` statement
            #with open(path) as f:
            #    source = f.read()
            source = open(path).read()
        else:
            source = current_namespace[0].read()
        if path.endswith('.py'):
            f = Module(path, source)
        else:
            f = builtin.Parser(path=path)
    else:
        f = builtin.Parser(name=path)

    return f.parser.top, rest
