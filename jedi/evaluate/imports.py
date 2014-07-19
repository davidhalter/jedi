"""
:mod:`jedi.evaluate.imports` is here to resolve import statements and return
the modules/classes/functions/whatever, which they stand for. However there's
not any actual importing done. This module is about finding modules in the
filesystem. This can be quite tricky sometimes, because Python imports are not
always that simple.

This module uses imp for python up to 3.2 and importlib for python 3.3 on; the
correct implementation is delegated to _compatibility.

This module also supports import autocompletion, which means to complete
statements like ``from datetim`` (curser at the end would return ``datetime``).
"""
import os
import pkgutil
import sys
from itertools import chain

from jedi._compatibility import find_module, unicode
from jedi import common
from jedi import debug
from jedi import cache
from jedi.parser import fast
from jedi.parser import representation as pr
from jedi.evaluate.sys_path import get_sys_path, sys_path_with_modifications
from jedi.evaluate import helpers
from jedi import settings
from jedi.common import source_to_unicode
from jedi.evaluate import compiled
from jedi.evaluate import analysis
from jedi.evaluate.cache import memoize_default, NO_DEFAULT


class ModuleNotFound(Exception):
    def __init__(self, name_part):
        super(ModuleNotFound, self).__init__()
        self.name_part = name_part


class ImportWrapper(pr.Base):
    """
    An ImportWrapper is the path of a `pr.Import` object.
    """
    class GlobalNamespace(object):
        def __init__(self):
            self.line_offset = 0

    GlobalNamespace = GlobalNamespace()

    def __init__(self, evaluator, import_stmt, is_like_search=False, kill_count=0,
                 nested_resolve=False, is_just_from=False):
        """
        :param is_like_search: If the wrapper is used for autocompletion.
        :param kill_count: Placement of the import, sometimes we only want to
            resole a part of the import.
        :param nested_resolve: Resolves nested imports fully.
        :param is_just_from: Bool if the second part is missing.
        """
        self._evaluator = evaluator
        self.import_stmt = import_stmt
        self.is_like_search = is_like_search
        self.nested_resolve = nested_resolve
        self.is_just_from = is_just_from

        self.is_partial_import = bool(max(0, kill_count))

        # rest is import_path resolution
        import_path = []
        if import_stmt.from_ns:
            import_path += import_stmt.from_ns.names
        if import_stmt.namespace:
            if self.import_stmt.is_nested() and not nested_resolve:
                import_path.append(import_stmt.namespace.names[0])
            else:
                import_path += import_stmt.namespace.names

        for i in range(kill_count + int(is_like_search)):
            if import_path:
                import_path.pop()

        module = import_stmt.get_parent_until()
        self._importer = get_importer(self._evaluator, tuple(import_path), module,
                                      import_stmt.relative_count)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.import_stmt)

    @property
    def import_path(self):
        return self._importer.str_import_path()

    def get_defined_names(self, on_import_stmt=False):
        names = []
        for scope in self.follow():
            if scope is ImportWrapper.GlobalNamespace:
                if not self._is_relative_import():
                    names += self._get_module_names()

                if self._importer.file_path is not None:
                    path = os.path.abspath(self._importer.file_path)
                    for i in range(self.import_stmt.relative_count - 1):
                        path = os.path.dirname(path)
                    names += self._get_module_names([path])

                    if self._is_relative_import():
                        rel_path = os.path.join(self._importer.get_relative_path(),
                                                '__init__.py')
                        if os.path.exists(rel_path):
                            m = _load_module(rel_path)
                            names += m.get_defined_names()
            else:
                if on_import_stmt and isinstance(scope, pr.Module) \
                        and scope.path.endswith('__init__.py'):
                    pkg_path = os.path.dirname(scope.path)
                    paths = self._importer.namespace_packages(pkg_path,
                                                              self.import_path)
                    names += self._get_module_names([pkg_path] + paths)
                if self.is_just_from:
                    # In the case of an import like `from x.` we don't need to
                    # add all the variables.
                    if ('os',) == self.import_path and not self._is_relative_import():
                        # os.path is a hardcoded exception, because it's a
                        # ``sys.modules`` modification.
                        names.append(self._generate_name('path'))
                    continue
                from jedi.evaluate import finder
                for s, scope_names in finder.get_names_of_scope(self._evaluator,
                                                                scope, include_builtin=False):
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

    def _generate_name(self, name):
        return helpers.FakeName(name, parent=self.import_stmt)

    def _get_module_names(self, search_path=None):
        """
        Get the names of all modules in the search_path. This means file names
        and not names defined in the files.
        """

        names = []
        # add builtin module names
        if search_path is None:
            names += [self._generate_name(name) for name in sys.builtin_module_names]

        if search_path is None:
            search_path = self._importer.sys_path_with_modifications()
        for module_loader, name, is_pkg in pkgutil.iter_modules(search_path):
            names.append(self._generate_name(name))
        return names

    def _is_relative_import(self):
        return bool(self.import_stmt.relative_count)

    def follow(self, is_goto=False):
        if self._evaluator.recursion_detector.push_stmt(self.import_stmt):
            # check recursion
            return []

        if self.import_path:
            try:
                module, rest = self._importer.follow_file_system()
            except ModuleNotFound as e:
                analysis.add(self._evaluator, 'import-error', e.name_part)
                return []

            if self.import_stmt.is_nested() and not self.nested_resolve:
                scopes = [NestedImportModule(module, self.import_stmt)]
            else:
                scopes = [module]

            star_imports = remove_star_imports(self._evaluator, module)
            if star_imports:
                scopes = [StarImportModule(scopes[0], star_imports)]

            # follow the rest of the import (not FS -> classes, functions)
            if len(rest) > 1 or rest and self.is_like_search:
                scopes = []
                if ('os', 'path') == self.import_path[:2] \
                        and not self._is_relative_import():
                    # This is a huge exception, we follow a nested import
                    # ``os.path``, because it's a very important one in Python
                    # that is being achieved by messing with ``sys.modules`` in
                    # ``os``.
                    scopes = self._evaluator.follow_path(iter(rest), [module], module)
            elif rest:
                if is_goto:
                    scopes = list(chain.from_iterable(
                        self._evaluator.find_types(s, rest[0], is_goto=True)
                        for s in scopes))
                else:
                    scopes = list(chain.from_iterable(
                        self._evaluator.follow_path(iter(rest), [s], s)
                        for s in scopes))
        else:
            scopes = [ImportWrapper.GlobalNamespace]
        debug.dbg('after import: %s', scopes)
        if not scopes:
            analysis.add(self._evaluator, 'import-error',
                         self._importer.import_path[-1])
        self._evaluator.recursion_detector.pop_stmt()
        return scopes


class NestedImportModule(pr.Module):
    def __init__(self, module, nested_import):
        self._module = module
        self._nested_import = nested_import

    def _get_nested_import_name(self):
        """
        Generates an Import statement, that can be used to fake nested imports.
        """
        i = self._nested_import
        # This is not an existing Import statement. Therefore, set position to
        # 0 (0 is not a valid line number).
        zero = (0, 0)
        names = [unicode(name_part) for name_part in i.namespace.names[1:]]
        name = helpers.FakeName(names, self._nested_import)
        new = pr.Import(i._sub_module, zero, zero, name)
        new.parent = self._module
        debug.dbg('Generated a nested import: %s', new)
        return helpers.FakeName(str(i.namespace.names[1]), new)

    def _get_defined_names(self):
        """
        NesteImportModule don't seem to be actively used, right now.
        However, they might in the future. If we do more sophisticated static
        analysis checks.
        """
        nested = self._get_nested_import_name()
        return self._module.get_defined_names() + [nested]

    def __getattr__(self, name):
        return getattr(self._module, name)

    def __repr__(self):
        return "<%s: %s of %s>" % (self.__class__.__name__, self._module,
                                   self._nested_import)


class StarImportModule(pr.Module):
    """
    Used if a module contains star imports.
    """
    def __init__(self, module, star_import_modules):
        self._module = module
        self.star_import_modules = star_import_modules

    def scope_names_generator(self, position=None):
        for module, names in self._module.scope_names_generator(position):
            yield module, names
        for s in self.star_import_modules:
            yield s, s.get_defined_names()

    def __getattr__(self, name):
        return getattr(self._module, name)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self._module)


def get_importer(evaluator, import_path, module, level=0):
    """
    Checks the evaluator caches first, which resembles the ``sys.modules``
    cache and speeds up libraries like ``numpy``.
    """
    if level != 0:
        # Only absolute imports should be cached. Otherwise we have a mess.
        # TODO Maybe calculate the absolute import and save it here?
        return _Importer(evaluator, import_path, module, level)
    try:
        return evaluator.import_cache[import_path]
    except KeyError:
        importer = _Importer(evaluator, import_path, module, level)
        evaluator.import_cache[import_path] = importer
        return importer


class _Importer(object):
    def __init__(self, evaluator, import_path, module, level=0):
        """
        An implementation similar to ``__import__``. Use `follow_file_system`
        to actually follow the imports.

        *level* specifies whether to use absolute or relative imports. 0 (the
        default) means only perform absolute imports. Positive values for level
        indicate the number of parent directories to search relative to the
        directory of the module calling ``__import__()`` (see PEP 328 for the
        details).

        :param import_path: List of namespaces (strings).
        """
        debug.speed('import %s' % (import_path,))
        self._evaluator = evaluator
        self.import_path = import_path
        self.level = level
        self.module = module
        path = module.path
        # TODO abspath
        self.file_path = os.path.dirname(path) if path is not None else None

    def str_import_path(self):
        """Returns the import path as pure strings instead of NameParts."""
        return tuple(str(name_part) for name_part in self.import_path)

    def get_relative_path(self):
        path = self.file_path
        for i in range(self.level - 1):
            path = os.path.dirname(path)
        return path

    @memoize_default()
    def sys_path_with_modifications(self):
        # If you edit e.g. gunicorn, there will be imports like this:
        # `from gunicorn import something`. But gunicorn is not in the
        # sys.path. Therefore look if gunicorn is a parent directory, #56.
        in_path = []
        if self.import_path:
            parts = self.file_path.split(os.path.sep)
            for i, p in enumerate(parts):
                if p == unicode(self.import_path[0]):
                    new = os.path.sep.join(parts[:i])
                    in_path.append(new)

        return in_path + sys_path_with_modifications(self._evaluator, self.module)

    def follow(self, evaluator):
        scope, rest = self.follow_file_system()
        if rest:
            # follow the rest of the import (not FS -> classes, functions)
            return evaluator.follow_path(iter(rest), [scope], scope)
        return [scope]

    @memoize_default(NO_DEFAULT)
    def follow_file_system(self):
        if self.file_path:
            sys_path_mod = list(self.sys_path_with_modifications())
            if not self.module.has_explicit_absolute_import:
                # If the module explicitly asks for absolute imports,
                # there's probably a bogus local one.
                sys_path_mod.insert(0, self.file_path)

            # First the sys path is searched normally and if that doesn't
            # succeed, try to search the parent directories, because sometimes
            # Jedi doesn't recognize sys.path modifications (like py.test
            # stuff).
            old_path, temp_path = self.file_path, os.path.dirname(self.file_path)
            while old_path != temp_path:
                sys_path_mod.append(temp_path)
                old_path, temp_path = temp_path, os.path.dirname(temp_path)
        else:
            sys_path_mod = list(get_sys_path())

        from jedi.evaluate.representation import ModuleWrapper
        module, rest = self._follow_sys_path(sys_path_mod)
        if isinstance(module, pr.Module):
            return ModuleWrapper(self._evaluator, module), rest
        return module, rest

    def namespace_packages(self, found_path, import_path):
        """
        Returns a list of paths of possible ``pkgutil``/``pkg_resources``
        namespaces. If the package is no "namespace package", an empty list is
        returned.
        """
        def follow_path(directories, paths):
            try:
                directory = next(directories)
            except StopIteration:
                return paths
            else:
                deeper_paths = []
                for p in paths:
                    new = os.path.join(p, directory)
                    if os.path.isdir(new) and new != found_path:
                        deeper_paths.append(new)
                return follow_path(directories, deeper_paths)

        with open(os.path.join(found_path, '__init__.py'), 'rb') as f:
            content = common.source_to_unicode(f.read())
            # these are strings that need to be used for namespace packages,
            # the first one is ``pkgutil``, the second ``pkg_resources``.
            options = ('declare_namespace(__name__)', 'extend_path(__path__')
            if options[0] in content or options[1] in content:
                # It is a namespace, now try to find the rest of the modules.
                return follow_path(iter(import_path), sys.path)
        return []

    def _follow_sys_path(self, sys_path):
        """
        Find a module with a path (of the module, like usb.backend.libusb10).
        """
        def follow_str(ns_path, string):
            debug.dbg('follow_module %s %s', ns_path, string)
            path = None
            if ns_path:
                path = ns_path
            elif self.level > 0:  # is a relative import
                path = self.get_relative_path()

            if path is not None:
                importing = find_module(string, [path])
            else:
                debug.dbg('search_module %s %s', string, self.file_path)
                # Override the sys.path. It works only good that way.
                # Injecting the path directly into `find_module` did not work.
                sys.path, temp = sys_path, sys.path
                try:
                    importing = find_module(string)
                finally:
                    sys.path = temp

            return importing

        current_namespace = (None, None, None)
        # now execute those paths
        rest = []
        for i, s in enumerate(self.import_path):
            try:
                current_namespace = follow_str(current_namespace[1], unicode(s))
            except ImportError:
                _continue = False
                if self.level >= 1 and len(self.import_path) == 1:
                    # follow `from . import some_variable`
                    rel_path = self.get_relative_path()
                    with common.ignored(ImportError):
                        current_namespace = follow_str(rel_path, '__init__')
                elif current_namespace[2]:  # is a package
                    path = self.str_import_path()[:i]
                    for n in self.namespace_packages(current_namespace[1], path):
                        try:
                            current_namespace = follow_str(n, unicode(s))
                            if current_namespace[1]:
                                _continue = True
                                break
                        except ImportError:
                            pass

                if not _continue:
                    if current_namespace[1]:
                        rest = self.str_import_path()[i:]
                        break
                    else:
                        raise ModuleNotFound(s)

        path = current_namespace[1]
        is_package_directory = current_namespace[2]

        f = None
        if is_package_directory or current_namespace[0]:
            # is a directory module
            if is_package_directory:
                path = os.path.join(path, '__init__.py')
                with open(path, 'rb') as f:
                    source = f.read()
            else:
                source = current_namespace[0].read()
                current_namespace[0].close()
            return _load_module(path, source, sys_path=sys_path), rest
        else:
            return _load_module(name=path, sys_path=sys_path), rest


def follow_imports(evaluator, scopes):
    """
    Here we strip the imports - they don't get resolved necessarily.
    Really used anymore? Merge with remove_star_imports?
    """
    result = []
    for s in scopes:
        if isinstance(s, pr.Import):
            for r in ImportWrapper(evaluator, s).follow():
                result.append(r)
        else:
            result.append(s)
    return result


@cache.cache_star_import
def remove_star_imports(evaluator, scope, ignored_modules=()):
    """
    Check a module for star imports::

        from module import *

    and follow these modules.
    """
    if isinstance(scope, StarImportModule):
        return scope.star_import_modules
    modules = follow_imports(evaluator, (i for i in scope.get_imports() if i.star))
    new = []
    for m in modules:
        if m not in ignored_modules:
            new += remove_star_imports(evaluator, m, modules)
    modules += new

    # Filter duplicate modules.
    return set(modules)


def _load_module(path=None, source=None, name=None, sys_path=None):
    def load(source):
        dotted_path = path and compiled.dotted_from_fs_path(path, sys_path)
        if path is not None and path.endswith('.py') \
                and not dotted_path in settings.auto_import_modules:
            if source is None:
                with open(path, 'rb') as f:
                    source = f.read()
        else:
            return compiled.load_module(path, name)
        p = path or name
        p = fast.FastParser(common.source_to_unicode(source), p)
        cache.save_parser(path, name, p)
        return p.module

    cached = cache.load_parser(path, name)
    return load(source) if cached is None else cached.module


def get_modules_containing_name(mods, name):
    """
    Search a name in the directories of modules.
    """
    def check_python_file(path):
        try:
            return cache.parser_cache[path].parser.module
        except KeyError:
            try:
                return check_fs(path)
            except IOError:
                return None

    def check_fs(path):
        with open(path, 'rb') as f:
            source = source_to_unicode(f.read())
            if name in source:
                return _load_module(path, source)

    # skip non python modules
    mods = set(m for m in mods if not isinstance(m, compiled.CompiledObject))
    mod_paths = set()
    for m in mods:
        mod_paths.add(m.path)
        yield m

    if settings.dynamic_params_for_other_modules:
        paths = set(settings.additional_dynamic_modules)
        for p in mod_paths:
            if p is not None:
                d = os.path.dirname(p)
                for entry in os.listdir(d):
                    if entry not in mod_paths:
                        if entry.endswith('.py'):
                            paths.add(d + os.path.sep + entry)

        for p in sorted(paths):
            # make testing easier, sort it - same results on every interpreter
            c = check_python_file(p)
            if c is not None and c not in mods:
                yield c
