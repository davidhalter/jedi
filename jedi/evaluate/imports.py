"""
:mod:`jedi.evaluate.imports` is here to resolve import statements and return
the modules/classes/functions/whatever, which they stand for. However there's
not any actual importing done. This module is about finding modules in the
filesystem. This can be quite tricky sometimes, because Python imports are not
always that simple.

This module uses imp for python up to 3.2 and importlib for python 3.3 on; the
correct implementation is delegated to _compatibility.

This module also supports import autocompletion, which means to complete
statements like ``from datetim`` (cursor at the end would return ``datetime``).
"""
import os

from parso.python import tree
from parso.tree import search_ancestor
from parso import python_bytes_to_unicode
from parso.file_io import KnownContentFileIO

from jedi._compatibility import (FileNotFoundError, ImplicitNSInfo,
                                 force_unicode, unicode)
from jedi import debug
from jedi import settings
from jedi.parser_utils import get_cached_code_lines
from jedi.evaluate import sys_path
from jedi.evaluate import helpers
from jedi.evaluate import compiled
from jedi.evaluate import analysis
from jedi.evaluate.utils import unite
from jedi.evaluate.cache import evaluator_method_cache
from jedi.evaluate.filters import AbstractNameDefinition
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
from jedi.evaluate.gradual.typeshed import import_module_decorator


class ModuleCache(object):
    def __init__(self):
        self._path_cache = {}
        self._name_cache = {}

    def add(self, string_names, context_set):
        #path = module.py__file__()
        #self._path_cache[path] = context_set
        if string_names is not None:
            self._name_cache[string_names] = context_set

    def get(self, string_names):
        return self._name_cache[string_names]

    def get_from_path(self, path):
        return self._path_cache[path]


# This memoization is needed, because otherwise we will infinitely loop on
# certain imports.
@evaluator_method_cache(default=NO_CONTEXTS)
def infer_import(context, tree_name, is_goto=False):
    module_context = context.get_root_context()
    import_node = search_ancestor(tree_name, 'import_name', 'import_from')
    import_path = import_node.get_path_for_name(tree_name)
    from_import_name = None
    evaluator = context.evaluator
    try:
        from_names = import_node.get_from_names()
    except AttributeError:
        # Is an import_name
        pass
    else:
        if len(from_names) + 1 == len(import_path):
            # We have to fetch the from_names part first and then check
            # if from_names exists in the modules.
            from_import_name = import_path[-1]
            import_path = from_names

    importer = Importer(evaluator, tuple(import_path),
                        module_context, import_node.level)

    types = importer.follow()

    #if import_node.is_nested() and not self.nested_resolve:
    #    scopes = [NestedImportModule(module, import_node)]

    if not types:
        return NO_CONTEXTS

    if from_import_name is not None:
        types = unite(
            t.py__getattribute__(
                from_import_name,
                name_context=context,
                is_goto=is_goto,
                analysis_errors=False
            )
            for t in types
        )
        if not is_goto:
            types = ContextSet(types)

        if not types:
            path = import_path + [from_import_name]
            importer = Importer(evaluator, tuple(path),
                                module_context, import_node.level)
            types = importer.follow()
            # goto only accepts `Name`
            if is_goto:
                types = set(s.name for s in types)
    else:
        # goto only accepts `Name`
        if is_goto:
            types = set(s.name for s in types)

    debug.dbg('after import: %s', types)
    return types


class NestedImportModule(tree.Module):
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
        new = tree.Import(i._sub_module, zero, zero, name)
        new.parent = self._module
        debug.dbg('Generated a nested import: %s', new)
        return helpers.FakeName(str(i.namespace_names[1]), new)

    def __getattr__(self, name):
        return getattr(self._module, name)

    def __repr__(self):
        return "<%s: %s of %s>" % (self.__class__.__name__, self._module,
                                   self._nested_import)


def _add_error(context, name, message):
    if hasattr(name, 'parent') and context is not None:
        analysis.add(context, 'import-error', name, message)
    else:
        debug.warning('ImportError without origin: ' + message)


class ImportName(AbstractNameDefinition):
    start_pos = (1, 0)
    _level = 0

    def __init__(self, parent_context, string_name):
        self.parent_context = parent_context
        self.string_name = string_name

    def infer(self):
        return Importer(
            self.parent_context.evaluator,
            [self.string_name],
            self.parent_context,
            level=self._level,
        ).follow()

    def goto(self):
        return [m.name for m in self.infer()]

    def get_root_context(self):
        # Not sure if this is correct.
        return self.parent_context.get_root_context()

    @property
    def api_type(self):
        return 'module'


class SubModuleName(ImportName):
    _level = 1


class OsPathName(ImportName):
    def infer(self):
        return self.parent_context.evaluator.import_module(('os', 'path'))


def _level_to_base_import_path(project_path, directory, level):
    """
    In case the level is outside of the currently known package (something like
    import .....foo), we can still try our best to help the user for
    completions.
    """
    for i in range(level - 1):
        old = directory
        directory = os.path.dirname(directory)
        if old == directory:
            return None, None

    d = directory
    level_import_paths = []
    # Now that we are on the level that the user wants to be, calculate the
    # import path for it.
    while True:
        if d == project_path:
            return level_import_paths, d
        dir_name = os.path.basename(d)
        if dir_name:
            level_import_paths.insert(0, dir_name)
            d = os.path.dirname(d)
        else:
            return None, directory


class Importer(object):
    def __init__(self, evaluator, import_path, module_context, level=0):
        """
        An implementation similar to ``__import__``. Use `follow`
        to actually follow the imports.

        *level* specifies whether to use absolute or relative imports. 0 (the
        default) means only perform absolute imports. Positive values for level
        indicate the number of parent directories to search relative to the
        directory of the module calling ``__import__()`` (see PEP 328 for the
        details).

        :param import_path: List of namespaces (strings or Names).
        """
        debug.speed('import %s %s' % (import_path, module_context))
        self._evaluator = evaluator
        self.level = level
        self.module_context = module_context

        self._fixed_sys_path = None
        self._inference_possible = True
        if level:
            base = module_context.py__package__()
            if base == [''] or base == ['__main__']:
                raise NotImplementedError(module_context.py__package__())
                base = []
            # We need to care for two cases, the first one is if it's a valid
            # Python import. This import has a properly defined module name
            # chain like `foo.bar.baz` and an import in baz is made for
            # `..lala.` It can then resolve to `foo.bar.lala`.
            # The else here is a heuristic for all other cases, if for example
            # in `foo` you search for `...bar`, it's obviously out of scope.
            # However since Jedi tries to just do it's best, we help the user
            # here, because he might have specified something wrong in his
            # project.
            if level <= len(base):
                # Here we basically rewrite the level to 0.
                base = tuple(base)
                if level > 1:
                    base = base[:-level + 1]
                import_path = base + tuple(import_path)
            else:
                path = module_context.py__file__()
                import_path = list(import_path)
                if path is None:
                    # If no path is defined, our best case is that the current
                    # file is edited by a user on the current working
                    # directory. We need to add an initial path, because it
                    # will get removed as the name of the current file.
                    directory = os.getcwd()
                else:
                    directory = os.path.dirname(path)

                base_import_path, base_directory = _level_to_base_import_path(
                    self._evaluator.project._path, directory, level,
                )
                if base_directory is None:
                    # Everything is lost, the relative import does point
                    # somewhere out of the filesystem.
                    self._inference_possible = False
                else:
                    self._fixed_sys_path = [force_unicode(base_directory)]

                if base_import_path is None:
                    if import_path:
                        _add_error(
                            module_context, import_path[0],
                            message='Attempted relative import beyond top-level package.'
                        )
                else:
                    import_path = base_import_path + import_path
        self.import_path = import_path

    @property
    def _str_import_path(self):
        """Returns the import path as pure strings instead of `Name`."""
        return tuple(
            name.value if isinstance(name, tree.Name) else name
            for name in self.import_path
        )

    def _sys_path_with_modifications(self):
        if self._fixed_sys_path is not None:
            return self._fixed_sys_path

        sys_path_mod = (
            self._evaluator.get_sys_path()
            + sys_path.check_sys_path_modifications(self.module_context)
        )

        if self._evaluator.environment.version_info.major == 2:
            file_path = self.module_context.py__file__()
            if file_path is not None:
                # Python2 uses an old strange way of importing relative imports.
                sys_path_mod.append(force_unicode(os.path.dirname(file_path)))

        return sys_path_mod

    def follow(self):
        if not self.import_path or not self._evaluator.infer_enabled \
                or not self._inference_possible:
            return NO_CONTEXTS

        import_names = tuple(
            force_unicode(i.value if isinstance(i, tree.Name) else i)
            for i in self.import_path
        )

        context_set = [None]
        for i, name in enumerate(self.import_path):
            try:
                context_set = ContextSet.from_sets([
                    self._evaluator.import_module(
                        import_names[:i+1],
                        parent_module_context,
                        self._sys_path_with_modifications(),
                    )
                    for parent_module_context in context_set
                ])
            except JediImportError:
                message = 'No module named ' + '.'.join(import_names)
                _add_error(self.module_context, name, message)
                return NO_CONTEXTS
        return context_set

    def _get_module_names(self, search_path=None, in_module=None):
        """
        Get the names of all modules in the search_path. This means file names
        and not names defined in the files.
        """
        sub = self._evaluator.compiled_subprocess

        names = []
        # add builtin module names
        if search_path is None and in_module is None:
            names += [ImportName(self.module_context, name)
                      for name in sub.get_builtin_module_names()]

        if search_path is None:
            search_path = self._sys_path_with_modifications()

        for name in sub.list_module_names(search_path):
            if in_module is None:
                n = ImportName(self.module_context, name)
            else:
                n = SubModuleName(in_module, name)
            names.append(n)
        return names

    def completion_names(self, evaluator, only_modules=False):
        """
        :param only_modules: Indicates wheter it's possible to import a
            definition that is not defined in a module.
        """
        if not self._inference_possible:
            return []

        names = []
        if self.import_path:
            # flask
            if self._str_import_path == ('flask', 'ext'):
                # List Flask extensions like ``flask_foo``
                for mod in self._get_module_names():
                    modname = mod.string_name
                    if modname.startswith('flask_'):
                        extname = modname[len('flask_'):]
                        names.append(ImportName(self.module_context, extname))
                # Now the old style: ``flaskext.foo``
                for dir in self._sys_path_with_modifications():
                    flaskext = os.path.join(dir, 'flaskext')
                    if os.path.isdir(flaskext):
                        names += self._get_module_names([flaskext])

            for context in self.follow():
                # Non-modules are not completable.
                if context.api_type != 'module':  # not a module
                    continue
                # namespace packages
                try:
                    path_method = context.py__path__
                except AttributeError:
                    pass
                else:
                    # For implicit namespace packages and module names.
                    names += self._get_module_names(path_method(), in_module=context)

                if only_modules:
                    # In the case of an import like `from x.` we don't need to
                    # add all the variables.
                    if ('os',) == self._str_import_path and not self.level:
                        # os.path is a hardcoded exception, because it's a
                        # ``sys.modules`` modification.
                        names.append(OsPathName(context, 'path'))
                    continue

                for filter in context.get_filters(search_global=False):
                    names += filter.values()
        else:
            if self.level:
                # We only get here if the level cannot be properly calculated.
                names += self._get_module_names(self._fixed_sys_path)
            else:
                # This is just the list of global imports.
                names += self._get_module_names()
        return names


class JediImportError(Exception):
    def __init__(self, import_names):
        self.import_names = import_names


@import_module_decorator
def import_module(evaluator, import_names, parent_module_context, sys_path, load_stub=True):
    """
    This method is very similar to importlib's `_gcd_import`.
    """
    if import_names[0] in settings.auto_import_modules:
        module = _load_builtin_module(evaluator, import_names, sys_path)
        return ContextSet([module])

    module_name = '.'.join(import_names)
    if parent_module_context is None:
        # Override the sys.path. It works only good that way.
        # Injecting the path directly into `find_module` did not work.
        file_io_or_ns, is_pkg = evaluator.compiled_subprocess.get_module_info(
            string=import_names[-1],
            full_name=module_name,
            sys_path=sys_path,
            is_global_search=True,
        )
        if is_pkg is None:
            raise JediImportError(import_names)
    else:
        try:
            method = parent_module_context.py__path__
        except AttributeError:
            # The module is not a package.
            raise JediImportError(import_names)
        else:
            paths = method()
            for path in paths:
                # At the moment we are only using one path. So this is
                # not important to be correct.
                if not isinstance(path, list):
                    path = [path]
                file_io_or_ns, is_pkg = evaluator.compiled_subprocess.get_module_info(
                    string=import_names[-1],
                    path=path,
                    full_name=module_name,
                    is_global_search=False,
                )
                if is_pkg is not None:
                    break
            else:
                raise JediImportError(import_names)

    if isinstance(file_io_or_ns, ImplicitNSInfo):
        from jedi.evaluate.context.namespace import ImplicitNamespaceContext
        module = ImplicitNamespaceContext(
            evaluator,
            fullname=file_io_or_ns.name,
            paths=file_io_or_ns.paths,
        )
    elif file_io_or_ns is None:
        module = _load_builtin_module(evaluator, import_names, sys_path)
    else:
        module = _load_python_module(
            evaluator, file_io_or_ns, sys_path,
            import_names=import_names,
            is_package=is_pkg,
        )

    if parent_module_context is None:
        debug.dbg('global search_module %s: %s', import_names[-1], module)
    else:
        debug.dbg('search_module %s in paths %s: %s', module_name, paths, module)
    return ContextSet([module])


def _load_python_module(evaluator, file_io, sys_path=None,
                        import_names=None, is_package=False):
    try:
        return evaluator.module_cache.get_from_path(file_io.path)
    except KeyError:
        pass

    module_node = evaluator.parse(
        file_io=file_io,
        cache=True,
        diff_cache=settings.fast_parser,
        cache_path=settings.cache_directory
    )

    from jedi.evaluate.context import ModuleContext
    return ModuleContext(
        evaluator, module_node,
        path=file_io.path,
        string_names=import_names,
        code_lines=get_cached_code_lines(evaluator.grammar, file_io.path),
        is_package=is_package,
    )


def _load_builtin_module(evaluator, import_names=None, sys_path=None):
    if sys_path is None:
        sys_path = evaluator.get_sys_path()

    dotted_name = '.'.join(import_names)
    assert dotted_name is not None
    module = compiled.load_module(evaluator, dotted_name=dotted_name, sys_path=sys_path)
    if module is None:
        # The file might raise an ImportError e.g. and therefore not be
        # importable.
        raise JediImportError(import_names)
    return module


def get_modules_containing_name(evaluator, modules, name):
    """
    Search a name in the directories of modules.
    """
    def check_directory(path):
        d = os.path.dirname(os.path.abspath(path))
        for file_name in os.listdir(d):
            path = os.path.join(d, file_name)
            if file_name.endswith('.py'):
                yield path

    def check_fs(path, base_names):
        try:
            f = open(path, 'rb')
        except FileNotFoundError:
            return
        with f:
            code = python_bytes_to_unicode(f.read(), errors='replace')
            if name in code:
                e_sys_path = evaluator.get_sys_path()
                if base_names:
                    module_name = os.path.basename(path)
                    module_name = sys_path.remove_python_path_suffix(module_name)
                    is_package = module_name == '__init__'
                    if is_package:
                        raise NotImplementedError(
                            "This is probably not possible yet, please add a failing test first")
                        module_name = os.path.basename(os.path.dirname(path))
                    import_names = base_names + (module_name,)
                else:
                    import_names, is_package = sys_path.transform_path_to_dotted(e_sys_path, path)

                module = _load_python_module(
                    evaluator, KnownContentFileIO(path, code),
                    sys_path=e_sys_path,
                    import_names=import_names,
                    is_package=is_package,
                )
                evaluator.module_cache.add(import_names, ContextSet([module]))
                return module

    # skip non python modules
    used_mod_paths = set()
    path_with_names_to_be_checked = []
    for m in modules:
        try:
            path = m.py__file__()
        except AttributeError:
            pass
        else:
            if path is not None:
                if path not in used_mod_paths:
                    used_mod_paths.add(path)
                    path_with_names_to_be_checked.append((path, m.py__package__()))
        yield m

    if not settings.dynamic_params_for_other_modules:
        return

    for p in settings.additional_dynamic_modules:
        p = os.path.abspath(p)
        if p not in used_mod_paths:
            path_with_names_to_be_checked.append((p, None))

    for p, base_names in path_with_names_to_be_checked:
        for file_path in check_directory(p):
            m = check_fs(file_path, base_names)
            if m is not None and not isinstance(m, compiled.CompiledObject):
                yield m
