"""
:mod:`imports` is here to resolve import statements and return the
modules/classes/functions/whatever, which they stand for. However there's not
any actual importing done. This module is about finding modules in the
filesystem. This can be quite tricky sometimes, because Python imports are not
always that simple.

This module uses imp for python up to 3.2 and importlib for python 3.3 on; the
correct implementation is delegated to _compatibility.

This module also supports import autocompletion, which means to complete
statements like ``from datetim`` (curser at the end would return ``datetime``).
"""
from __future__ import with_statement

import os
import pkgutil
import sys
import itertools

from jedi._compatibility import find_module
from jedi import modules
from jedi import common
from jedi import debug
from jedi import parsing_representation as pr
from jedi import cache
import builtin
import evaluate

# for debugging purposes only
imports_processed = 0


class ModuleNotFound(Exception):
    pass


class ImportPath(pr.Base):
    """
    An ImportPath is the path of a `pr.Import` object.
    """
    class _GlobalNamespace(object):
        def __init__(self):
            self.start_pos = 0, 0
            self.line_offset = 0

        def get_defined_names(self):
            return []

        def get_imports(self):
            return []

        def get_parent_until(self):
            return None

    GlobalNamespace = _GlobalNamespace()

    def __init__(self, import_stmt, is_like_search=False, kill_count=0,
                                                    direct_resolve=False):
        self.import_stmt = import_stmt
        self.is_like_search = is_like_search
        self.direct_resolve = direct_resolve
        self.is_partial_import = bool(max(0, kill_count))
        path = import_stmt.get_parent_until().path
        self.file_path = os.path.dirname(path) if path is not None else None

        # rest is import_path resolution
        self.import_path = []
        if import_stmt.from_ns:
            self.import_path += import_stmt.from_ns.names
        if import_stmt.namespace:
            if self.is_nested_import() and not direct_resolve:
                self.import_path.append(import_stmt.namespace.names[0])
            else:
                self.import_path += import_stmt.namespace.names

        for i in range(kill_count + int(is_like_search)):
            self.import_path.pop()

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.import_stmt)

    def is_nested_import(self):
        """
        This checks for the special case of nested imports, without aliases and
        from statement::

            import foo.bar
        """
        return not self.import_stmt.alias and not self.import_stmt.from_ns \
                and len(self.import_stmt.namespace.names) > 1 \
                and not self.direct_resolve

    def get_nested_import(self, parent):
        """
        See documentation of `self.is_nested_import`.
        Generates an Import statement, that can be used to fake nested imports.
        """
        i = self.import_stmt
        # This is not an existing Import statement. Therefore, set position to
        # 0 (0 is not a valid line number).
        zero = (0, 0)
        names = i.namespace.names[1:]
        n = pr.Name(i._sub_module, names, zero, zero, self.import_stmt)
        new = pr.Import(i._sub_module, zero, zero, n)
        new.parent = parent
        debug.dbg('Generated a nested import: %s' % new)
        return new

    def get_defined_names(self, on_import_stmt=False):
        names = []
        for scope in self.follow():
            if scope is ImportPath.GlobalNamespace:
                if self.import_stmt.relative_count == 0:
                    names += self.get_module_names()

                if self.file_path is not None:
                    path = os.path.abspath(self.file_path)
                    for i in range(self.import_stmt.relative_count - 1):
                        path = os.path.dirname(path)
                    names += self.get_module_names([path])

                    if self.import_stmt.relative_count:
                        rel_path = self.get_relative_path() + '/__init__.py'
                        with common.ignored(IOError):
                            m = modules.Module(rel_path)
                            names += m.parser.module.get_defined_names()
            else:
                if on_import_stmt and isinstance(scope, pr.Module) \
                                        and scope.path.endswith('__init__.py'):
                    pkg_path = os.path.dirname(scope.path)
                    names += self.get_module_names([pkg_path])
                for s, scope_names in evaluate.get_names_of_scope(scope,
                                                    include_builtin=False):
                    for n in scope_names:
                        if self.import_stmt.from_ns is None \
                                            or self.is_partial_import:
                                # from_ns must be defined to access module
                                # values plus a partial import means that there
                                # is something after the import, which
                                # automatically implies that there must not be
                                # any non-module scope.
                                continue
                        names.append(n)
        return names

    def get_module_names(self, search_path=None):
        """
        Get the names of all modules in the search_path. This means file names
        and not names defined in the files.
        """
        if not search_path:
            search_path = self.sys_path_with_modifications()
        names = []
        for module_loader, name, is_pkg in pkgutil.iter_modules(search_path):
            inf_pos = (float('inf'), float('inf'))
            names.append(pr.Name(self.GlobalNamespace, [(name, inf_pos)],
                                        inf_pos, inf_pos, self.import_stmt))
        return names

    def sys_path_with_modifications(self):
        # If you edit e.g. gunicorn, there will be imports like this:
        # `from gunicorn import something`. But gunicorn is not in the
        # sys.path. Therefore look if gunicorn is a parent directory, #56.
        parts = self.file_path.split(os.path.sep)
        in_path = []
        if self.import_path:
            for i, p in enumerate(parts):
                if p == self.import_path[0]:
                    new = os.path.sep.join(parts[:i])
                    in_path.append(new)

        module = self.import_stmt.get_parent_until()
        return in_path + modules.sys_path_with_modifications(module)

    def follow(self, is_goto=False):
        """
        Returns the imported modules.
        """
        if evaluate.follow_statement.push_stmt(self.import_stmt):
            # check recursion
            return []

        if self.import_path:
            try:
                scope, rest = self._follow_file_system()
            except ModuleNotFound:
                debug.warning('Module not found: ' + str(self.import_stmt))
                evaluate.follow_statement.pop_stmt()
                return []

            scopes = [scope]
            scopes += remove_star_imports(scope)

            # follow the rest of the import (not FS -> classes, functions)
            if len(rest) > 1 or rest and self.is_like_search:
                scopes = []
            elif rest:
                if is_goto:
                    scopes = itertools.chain.from_iterable(
                                evaluate.find_name(s, rest[0], is_goto=True)
                                for s in scopes)
                else:
                    scopes = itertools.chain.from_iterable(
                                        evaluate.follow_path(iter(rest), s, s)
                                        for s in scopes)
            scopes = list(scopes)

            if self.is_nested_import():
                scopes.append(self.get_nested_import(scope))
        else:
            scopes = [ImportPath.GlobalNamespace]
        debug.dbg('after import', scopes)

        evaluate.follow_statement.pop_stmt()
        return scopes

    def get_relative_path(self):
        path = self.file_path
        for i in range(self.import_stmt.relative_count - 1):
            path = os.path.dirname(path)
        return path

    def _follow_file_system(self):
        """
        Find a module with a path (of the module, like usb.backend.libusb10).
        """
        def follow_str(ns_path, string):
            debug.dbg('follow_module', ns_path, string)
            path = None
            if ns_path:
                path = ns_path
            elif self.import_stmt.relative_count:
                path = self.get_relative_path()

            global imports_processed
            imports_processed += 1
            importing = None
            if path is not None:
                importing = find_module(string, [path])
            else:
                debug.dbg('search_module', string, self.file_path)
                # Override the sys.path. It works only good that way.
                # Injecting the path directly into `find_module` did not work.
                sys.path, temp = sys_path_mod, sys.path
                try:
                    importing = find_module(string)
                except ImportError:
                    sys.path = temp
                    raise
                sys.path = temp

            return importing

        if self.file_path:
            sys_path_mod = list(self.sys_path_with_modifications())
            sys_path_mod.insert(0, self.file_path)
        else:
            sys_path_mod = list(modules.get_sys_path())

        def module_not_found():
            raise ModuleNotFound('The module you searched has not been found')

        current_namespace = (None, None, None)
        # now execute those paths
        rest = []
        for i, s in enumerate(self.import_path):
            try:
                current_namespace = follow_str(current_namespace[1], s)
            except ImportError:
                if self.import_stmt.relative_count \
                                and len(self.import_path) == 1:
                    # follow `from . import some_variable`
                    rel_path = self.get_relative_path()
                    with common.ignored(ImportError):
                        current_namespace = follow_str(rel_path, '__init__')
                if current_namespace[1]:
                    rest = self.import_path[i:]
                else:
                    module_not_found()

        if current_namespace == (None, None, False):
            module_not_found()

        sys_path_mod.pop(0)  # TODO why is this here?
        path = current_namespace[1]
        is_package_directory = current_namespace[2]

        f = None
        if is_package_directory or current_namespace[0]:
            # is a directory module
            if is_package_directory:
                path += '/__init__.py'
                with open(path) as f:
                    source = f.read()
            else:
                source = current_namespace[0].read()
                current_namespace[0].close()
            if path.endswith('.py'):
                f = modules.Module(path, source)
            else:
                f = builtin.BuiltinModule(path=path)
        else:
            f = builtin.BuiltinModule(name=path)

        return f.parser.module, rest


def strip_imports(scopes):
    """
    Here we strip the imports - they don't get resolved necessarily.
    Really used anymore? Merge with remove_star_imports?
    """
    result = []
    for s in scopes:
        if isinstance(s, pr.Import):
            result += ImportPath(s).follow()
        else:
            result.append(s)
    return result


@cache.cache_star_import
def remove_star_imports(scope, ignored_modules=()):
    """
    Check a module for star imports:
    >>> from module import *

    and follow these modules.
    """
    modules = strip_imports(i for i in scope.get_imports() if i.star)
    new = []
    for m in modules:
        if m not in ignored_modules:
            new += remove_star_imports(m, modules)
    modules += new

    # Filter duplicate modules.
    return set(modules)
