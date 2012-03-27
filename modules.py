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
    If the source is not given, it is loaded by load_module.

    :param source: The source code of the file.
    :param module_name: The module name of the file.
    """
    def __init__(self, module_name, source=None):
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
        if not self.source:
            if i[0]:  # is the file pointer
                self.source = open(i[0]).read()
                print self.source, 'yesssa'
            else:
                self.source = ''
                print 'shizzel'
        self._parser = parsing.PyFuzzyParser(self.source)
        return self._parser

    def get_line(self, line):
        if not self._line_cache:
            self._line_cache = self.source.split('\n')

        if 1 <= line <= len(self._line_cache):
            return self._line_cache[line - 1]
        else:
            return None


def follow_module(_import):
    """
    follows a module name and returns the parser.
    :param name: A name from the parser.
    :type name: parsing.Name
    """
    def follow_str(ns, string):
        print ns, string
        if ns:
            path = ns[1]
        else:
            path = module_find_path
            debug.dbg('search_module', string, path)
        i = imp.find_module(string, path)
        return i

    # set path together
    ns_list = []
    if _import.from_ns:
        ns_list += _import.from_ns.names
    if _import.namespace:
        ns_list += _import.namespace.names

    # now execute those paths
    current_namespace = None
    rest = None
    for i, s in enumerate(ns_list):
        try:
            current_namespace = follow_str(current_namespace, s)
        except ImportError:
            if current_namespace:
                rest = ns_list[i:]
            else:
                raise ModuleNotFound(
                        'The module you searched has not been found')

    print 'yay', current_namespace
    f = File(current_namespace[2], current_namespace[0].read())
    out = f.parser.top.get_names()
    print out
    return parser
