from __future__ import with_statement

import os
import pkgutil
import imp
import sys
import weakref

import builtin
import modules
import debug
import parsing
import evaluate
import itertools


class ModuleNotFound(Exception):
    pass


class ImportPath(object):
    """
    An ImportPath is the path of a `parsing.Import` object.
    """
    class _GlobalNamespace(object):
        def get_defined_names(self):
            return []

        def get_imports(self):
            return []

    GlobalNamespace = _GlobalNamespace()

    def __init__(self, import_stmt, is_like_search=False, kill_count=0,
                                                    direct_resolve=False):
        self.import_stmt = import_stmt
        self.is_like_search = is_like_search
        self.direct_resolve = direct_resolve
        self.is_partial_import = bool(kill_count)
        self.file_path = os.path.dirname(import_stmt.get_parent_until().path)

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
        from statement:
        >>> import foo.bar
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
        # None.
        zero = (None, None)
        n = parsing.Name(i.namespace.names[1:], zero, zero)
        new = parsing.Import(zero, zero, n)
        new.parent = weakref.ref(parent)
        evaluate.faked_scopes.append(new)
        debug.dbg('Generated a nested import: %s' % new)
        return new

    def get_defined_names(self, on_import_stmt=False):
        names = []
        for scope in self.follow():
            if scope is ImportPath.GlobalNamespace:
                if self.import_stmt.relative_count == 0:
                    names += self.get_module_names()

                path = os.path.abspath(self.file_path)
                for i in range(self.import_stmt.relative_count - 1):
                    path = os.path.dirname(path)
                names += self.get_module_names([path])
            else:
                if on_import_stmt and isinstance(scope, parsing.Module) \
                                        and scope.path.endswith('__init__.py'):
                    pkg_path = os.path.dirname(scope.path)
                    names += self.get_module_names([pkg_path])
                for s, scope_names in evaluate.get_names_for_scope(scope,
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
            names.append(parsing.Name([(name, inf_pos)], inf_pos, inf_pos))
        return names

    def sys_path_with_modifications(self):
        module = self.import_stmt.get_parent_until()
        return modules.sys_path_with_modifications(module)

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
            scopes += itertools.chain.from_iterable(
                            remove_star_imports(s) for s in scopes)

            if len(rest) > 1 or rest and self.is_like_search:
                scopes = []
            elif rest:
                if is_goto:
                    scopes = itertools.chain.from_iterable(
                        evaluate.get_scopes_for_name(s, rest[0], is_goto=True)
                            for s in scopes)
                else:
                    scopes = evaluate.follow_path(iter(rest), scope)
            scopes = list(scopes)

            if self.is_nested_import():
                scopes.append(self.get_nested_import(scope))
        else:
            scopes = [ImportPath.GlobalNamespace]
        debug.dbg('after import', scopes)

        evaluate.follow_statement.pop_stmt()
        return scopes

    def _follow_file_system(self):
        """
        Find a module with a path (of the module, like usb.backend.libusb10).
        """
        def follow_str(ns, string):
            debug.dbg('follow_module', ns, string)
            path = None
            if ns:
                path = ns[1]
            elif self.import_stmt.relative_count:
                module = self.import_stmt.get_parent_until()
                path = os.path.abspath(module.path)
                for i in range(self.import_stmt.relative_count):
                    path = os.path.dirname(path)

            if path is not None:
                return imp.find_module(string, [path])
            else:
                debug.dbg('search_module', string, self.file_path)
                # Override the sys.path. It works only good that way.
                # Injecting the path directly into `find_module` did not work.
                sys.path, temp = sys_path_mod, sys.path
                try:
                    i = imp.find_module(string)
                except ImportError:
                    sys.path = temp
                    raise
                sys.path = temp
                return i

        sys_path_mod = self.sys_path_with_modifications()
        current_namespace = None
        sys_path_mod.insert(0, self.file_path)
        # now execute those paths
        rest = []
        for i, s in enumerate(self.import_path):
            try:
                current_namespace = follow_str(current_namespace, s)
            except ImportError:
                if current_namespace:
                    rest = self.import_path[i:]
                else:
                    raise ModuleNotFound(
                            'The module you searched has not been found')

        sys_path_mod.pop(0)
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
                f = modules.Module(path, source)
            else:
                f = builtin.Parser(path=path)
        else:
            f = builtin.Parser(name=path)

        return f.parser.module, rest


def strip_imports(scopes):
    """
    Here we strip the imports - they don't get resolved necessarily.
    Really used anymore? Merge with remove_star_imports?
    """
    result = []
    for s in scopes:
        if isinstance(s, parsing.Import):
            result += ImportPath(s).follow()
        else:
            result.append(s)
    return result


def remove_star_imports(scope, ignored_modules=[]):
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
