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
from jedi.parser import tree as pr
from jedi.evaluate.sys_path import get_sys_path, sys_path_with_modifications
from jedi.evaluate import helpers
from jedi import settings
from jedi.common import source_to_unicode
from jedi.evaluate import compiled
from jedi.evaluate import analysis
from jedi.evaluate.cache import memoize_default, NO_DEFAULT


class ModuleNotFound(Exception):
    def __init__(self, name):
        super(ModuleNotFound, self).__init__()
        self.name = name


def completion_names(evaluator, imp, pos):
    name = imp.name_for_position(pos)
    module = imp.get_parent_until()
    if name is None:
        level = 0
        for node in imp.children:
            if node.end_pos <= pos:
                if node in ('.', '...'):
                    level += len(node.value)
        import_path = []
    else:
        # Completion on an existing name.

        # The import path needs to be reduced by one, because we're completing.
        import_path = imp.path_for_name(name)[:-1]
        level = imp.level

    importer = get_importer(evaluator, tuple(import_path), module, level)
    if isinstance(imp, pr.ImportFrom):
        c = imp.children
        only_modules = c[c.index('import')].start_pos >= pos
    else:
        only_modules = True
    return importer.completion_names(evaluator, only_modules)


class ImportWrapper(pr.Base):
    def __init__(self, evaluator, name):
        self._evaluator = evaluator
        self._name = name

        self._import = name.get_parent_until(pr.Import)
        self.import_path = self._import.path_for_name(name)

    @memoize_default()
    def follow(self, is_goto=False):
        if self._evaluator.recursion_detector.push_stmt(self._import):
            # check recursion
            return []

        try:
            module = self._import.get_parent_until()
            import_path = self._import.path_for_name(self._name)
            importer = get_importer(self._evaluator, tuple(import_path),
                                    module, self._import.level)
            try:
                module, rest = importer.follow_file_system()
            except ModuleNotFound as e:
                analysis.add(self._evaluator, 'import-error', e.name)
                return []

            if module is None:
                return []

            #if self._import.is_nested() and not self.nested_resolve:
            #    scopes = [NestedImportModule(module, self._import)]
            scopes = [module]

            # goto only accepts `Name`
            if is_goto and not rest:
                scopes = [s.name for s in scopes]

            # follow the rest of the import (not FS -> classes, functions)
            if rest:
                if is_goto:
                    scopes = list(chain.from_iterable(
                        self._evaluator.find_types(s, rest[0], is_goto=True)
                        for s in scopes))
                else:
                    if self._import.type == 'import_from' \
                            or importer.str_import_path == ('os', 'path'):
                        scopes = importer.follow_rest(scopes[0], rest)
                    else:
                        scopes = []
            debug.dbg('after import: %s', scopes)
            if not scopes:
                analysis.add(self._evaluator, 'import-error', importer.import_path[-1])
        finally:
            self._evaluator.recursion_detector.pop_stmt()
        return scopes


class NestedImportModule(pr.Module):
    """
    TODO while there's no use case for nested import module right now, we might
        be able to use them for static analysis checks later on.
    """
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
        names = [unicode(name) for name in i.namespace_names[1:]]
        name = helpers.FakeName(names, self._nested_import)
        new = pr.Import(i._sub_module, zero, zero, name)
        new.parent = self._module
        debug.dbg('Generated a nested import: %s', new)
        return helpers.FakeName(str(i.namespace_names[1]), new)

    def __getattr__(self, name):
        return getattr(self._module, name)

    def __repr__(self):
        return "<%s: %s of %s>" % (self.__class__.__name__, self._module,
                                   self._nested_import)


def get_importer(evaluator, import_path, module, level=0):
    """
    Checks the evaluator caches first, which resembles the ``sys.modules``
    cache and speeds up libraries like ``numpy``.
    """
    import_path = tuple(import_path)  # We use it as hash in the import cache.
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

    @property
    def str_import_path(self):
        """Returns the import path as pure strings instead of `Name`."""
        return tuple(str(name) for name in self.import_path)

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
        if self.import_path and self.file_path is not None:
            parts = self.file_path.split(os.path.sep)
            for i, p in enumerate(parts):
                if p == unicode(self.import_path[0]):
                    new = os.path.sep.join(parts[:i])
                    in_path.append(new)

        return in_path + sys_path_with_modifications(self._evaluator, self.module)

    def follow(self, evaluator):
        try:
            scope, rest = self.follow_file_system()
        except ModuleNotFound:
            return []
        if rest:
            # follow the rest of the import (not FS -> classes, functions)
            return self.follow_rest(scope, rest)
        return [scope]

    def follow_rest(self, module, rest):
        # Either os.path or path length is smaller.
        if len(rest) < 2 or len(self.str_import_path) < 4 \
                and ('os', 'path') == self.str_import_path[:2] and self.level == 0:
            # This is a huge exception, we follow a nested import
            # ``os.path``, because it's a very important one in Python
            # that is being achieved by messing with ``sys.modules`` in
            # ``os``.
            scopes = [module]
            for r in rest:
                scopes = list(chain.from_iterable(
                              self._evaluator.find_types(s, r)
                              for s in scopes))
            return scopes
        else:
            return []

    @memoize_default(NO_DEFAULT)
    def follow_file_system(self):
        # Handle "magic" Flask extension imports:
        # ``flask.ext.foo`` is really ``flask_foo`` or ``flaskext.foo``.
        if len(self.import_path) > 2 and self.str_import_path[:2] == ('flask', 'ext'):
            orig_path = tuple(self.import_path)
            try:
                self.import_path = ('flask_' + str(orig_path[2]),) + orig_path[3:]
                return self._real_follow_file_system()
            except ModuleNotFound:
                self.import_path = ('flaskext',) + orig_path[2:]
                return self._real_follow_file_system()

        return self._real_follow_file_system()

    def _real_follow_file_system(self):
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
                return follow_path((str(i) for i in import_path), sys.path)
        return []

    def _follow_sys_path(self, sys_path):
        """
        Find a module with a path (of the module, like usb.backend.libusb10).
        """
        def follow_str(ns_path, string):
            debug.dbg('follow_module %s in %s', string, ns_path)
            path = None
            if ns_path:
                path = ns_path
            elif self.level > 0:  # is a relative import
                path = self.get_relative_path()

            if path is not None:
                importing = find_module(string, [path])
            else:
                debug.dbg('search_module %s in %s', string, self.file_path)
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
                    path = self.str_import_path[:i]
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
                        rest = self.str_import_path[i:]
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
            return _load_module(self._evaluator, path, source, sys_path=sys_path), rest
        else:
            return _load_module(self._evaluator, name=path, sys_path=sys_path), rest

    def _generate_name(self, name):
        return helpers.FakeName(name, parent=self.module)

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
            search_path = self.sys_path_with_modifications()
        for module_loader, name, is_pkg in pkgutil.iter_modules(search_path):
            names.append(self._generate_name(name))
        return names

    def completion_names(self, evaluator, only_modules=False):
        """
        :param only_modules: Indicates wheter it's possible to import a
            definition that is not defined in a module.
        """
        from jedi.evaluate import finder, representation as er
        names = []
        if self.import_path:
            # flask
            if self.str_import_path == ('flask', 'ext'):
                # List Flask extensions like ``flask_foo``
                for mod in self._get_module_names():
                    modname = str(mod)
                    if modname.startswith('flask_'):
                        extname = modname[len('flask_'):]
                        names.append(self._generate_name(extname))
                # Now the old style: ``flaskext.foo``
                for dir in self.sys_path_with_modifications():
                    flaskext = os.path.join(dir, 'flaskext')
                    if os.path.isdir(flaskext):
                        names += self._get_module_names([flaskext])

            for scope in self.follow(evaluator):
                # Non-modules are not completable.
                if not scope.type == 'file_input':  # not a module
                    continue

                # namespace packages
                if isinstance(scope, pr.Module) and scope.path.endswith('__init__.py'):
                    pkg_path = os.path.dirname(scope.path)
                    paths = self.namespace_packages(pkg_path, self.import_path)
                    names += self._get_module_names([pkg_path] + paths)

                if only_modules:
                    # In the case of an import like `from x.` we don't need to
                    # add all the variables.
                    if ('os',) == self.str_import_path and not self.level:
                        # os.path is a hardcoded exception, because it's a
                        # ``sys.modules`` modification.
                        names.append(self._generate_name('path'))

                    continue

                for names_dict in scope.names_dicts(search_global=False):
                    _names = list(chain.from_iterable(names_dict.values()))
                    if not _names:
                        continue
                    _names = finder.filter_definition_names(_names, scope)
                    names += _names
        else:
            # Empty import path=completion after import
            if not self.level:
                names += self._get_module_names()

            if self.file_path is not None:
                path = os.path.abspath(self.file_path)
                for i in range(self.level - 1):
                    path = os.path.dirname(path)
                names += self._get_module_names([path])

                if self.level:
                    rel_path = os.path.join(self.get_relative_path(),
                                            '__init__.py')
                    if os.path.exists(rel_path):
                        module = _load_module(self._evaluator, rel_path)
                        module = er.wrap(self._evaluator, module)
                        for names_dict in module.names_dicts(search_global=False):
                            names += chain.from_iterable(names_dict.values())
        return names


def _load_module(evaluator, path=None, source=None, name=None, sys_path=None):
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
        p = fast.FastParser(evaluator.grammar, common.source_to_unicode(source), p)
        cache.save_parser(path, name, p)
        return p.module

    cached = cache.load_parser(path, name)
    return load(source) if cached is None else cached.module


def get_modules_containing_name(evaluator, mods, name):
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
                return _load_module(evaluator, path, source)

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
            if c is not None and c not in mods and not isinstance(c, compiled.CompiledObject):
                yield c
