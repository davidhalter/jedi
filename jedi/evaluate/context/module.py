import re
import os

from parso import python_bytes_to_unicode

from jedi.evaluate.cache import evaluator_method_cache
from jedi._compatibility import iter_modules, all_suffixes
from jedi.evaluate.filters import GlobalNameFilter, ContextNameMixin, \
    AbstractNameDefinition, ParserTreeFilter, DictFilter, MergedFilter
from jedi.evaluate import compiled
from jedi.evaluate.base_context import TreeContext


class _ModuleAttributeName(AbstractNameDefinition):
    """
    For module attributes like __file__, __str__ and so on.
    """
    api_type = u'instance'

    def __init__(self, parent_module, string_name):
        self.parent_context = parent_module
        self.string_name = string_name

    def infer(self):
        return compiled.get_string_context_set(self.parent_context.evaluator)


class ModuleName(ContextNameMixin, AbstractNameDefinition):
    start_pos = 1, 0

    def __init__(self, context, name):
        self._context = context
        self._name = name

    @property
    def string_name(self):
        return self._name


class SubModuleDictMixin(object):
    @evaluator_method_cache()
    def _sub_modules_dict(self):
        """
        Lists modules in the directory of this module (if this module is a
        package).
        """
        from jedi.evaluate.imports import SubModuleName

        names = {}
        try:
            method = self.py__path__
        except AttributeError:
            pass
        else:
            for path in method():
                mods = self._iter_modules(path)
                for module_loader, name, is_pkg in mods:
                    # It's obviously a relative import to the current module.
                    names[name] = SubModuleName(self, name)

        # TODO add something like this in the future, its cleaner than the
        #   import hacks.
        # ``os.path`` is a hardcoded exception, because it's a
        # ``sys.modules`` modification.
        # if str(self.name) == 'os':
        #     names.append(Name('path', parent_context=self))

        return names

    def _iter_modules(self, path):
        return iter_modules([path])


class ModuleMixin(SubModuleDictMixin):
    def get_filters(self, search_global=False, until_position=None, origin_scope=None):
        yield MergedFilter(
            ParserTreeFilter(
                self.evaluator,
                context=self,
                until_position=until_position,
                origin_scope=origin_scope
            ),
            GlobalNameFilter(self, self.tree_node),
        )
        yield DictFilter(self._sub_modules_dict())
        yield DictFilter(self._module_attributes_dict())
        for star_filter in self.iter_star_filters():
            yield star_filter

    def py__class__(self):
        return compiled.get_special_object(self.evaluator, u'MODULE_CLASS')

    def is_module(self):
        return True

    @property
    @evaluator_method_cache()
    def name(self):
        return ModuleName(self, self._string_name)

    @property
    def _string_name(self):
        """ This is used for the goto functions. """
        # TODO It's ugly that we even use this, the name is usually well known
        # ahead so just pass it when create a ModuleContext.
        if self._path is None:
            return ''  # no path -> empty name
        else:
            sep = (re.escape(os.path.sep),) * 2
            r = re.search(r'([^%s]*?)(%s__init__)?(\.pyi?|\.so)?$' % sep, self._path)
            # Remove PEP 3149 names
            return re.sub(r'\.[a-z]+-\d{2}[mud]{0,3}$', '', r.group(1))

    @evaluator_method_cache()
    def _module_attributes_dict(self):
        names = ['__file__', '__package__', '__doc__', '__name__']
        # All the additional module attributes are strings.
        return dict((n, _ModuleAttributeName(self, n)) for n in names)

    def iter_star_filters(self, search_global=False):
        for star_module in self.star_imports():
            yield next(star_module.get_filters(search_global))

    # I'm not sure if the star import cache is really that effective anymore
    # with all the other really fast import caches. Recheck. Also we would need
    # to push the star imports into Evaluator.module_cache, if we reenable this.
    @evaluator_method_cache([])
    def star_imports(self):
        from jedi.evaluate.imports import infer_import

        modules = []
        for i in self.tree_node.iter_imports():
            if i.is_star_import():
                name = i.get_paths()[-1][-1]
                new = infer_import(self, name)
                for module in new:
                    if isinstance(module, ModuleContext):
                        modules += module.star_imports()
                modules += new
        return modules

    def get_qualified_names(self):
        """
        A module doesn't have a qualified name, but it's important to note that
        it's reachable and not `None`. With this information we can add
        qualified names on top for all context children.
        """
        return []


class ModuleContext(ModuleMixin, TreeContext):
    api_type = u'module'
    parent_context = None

    def __init__(self, evaluator, module_node, path, string_names, code_lines, is_package=False):
        super(ModuleContext, self).__init__(
            evaluator,
            parent_context=None,
            tree_node=module_node
        )
        self._path = path
        self.string_names = string_names
        self.code_lines = code_lines
        self.is_package = is_package

    def is_stub(self):
        if self._path is not None and self._path.endswith('.pyi'):
            # Currently this is the way how we identify stubs when e.g. goto is
            # used in them. This could be changed if stubs would be identified
            # sooner and used as StubOnlyModuleContext.
            return True
        return super(ModuleContext, self).is_stub()

    def py__name__(self):
        if self.string_names is None:
            return None
        return '.'.join(self.string_names)

    def py__file__(self):
        """
        In contrast to Python's __file__ can be None.
        """
        if self._path is None:
            return None

        return os.path.abspath(self._path)

    def py__package__(self):
        if self.is_package:
            return self.string_names
        return self.string_names[:-1]

    def _py__path__(self):
        # A namespace package is typically auto generated and ~10 lines long.
        first_few_lines = ''.join(self.code_lines[:50])
        # these are strings that need to be used for namespace packages,
        # the first one is ``pkgutil``, the second ``pkg_resources``.
        options = ('declare_namespace(__name__)', 'extend_path(__path__')
        if options[0] in first_few_lines or options[1] in first_few_lines:
            # It is a namespace, now try to find the rest of the
            # modules on sys_path or whatever the search_path is.
            paths = set()
            for s in self.evaluator.get_sys_path():
                other = os.path.join(s, self.name.string_name)
                if os.path.isdir(other):
                    paths.add(other)
            if paths:
                return list(paths)
            # Nested namespace packages will not be supported. Nobody ever
            # asked for it and in Python 3 they are there without using all the
            # crap above.

        # Default to the of this file.
        file = self.py__file__()
        assert file is not None  # Shouldn't be a package in the first place.
        return [os.path.dirname(file)]

    @property
    def py__path__(self):
        """
        Not seen here, since it's a property. The callback actually uses a
        variable, so use it like::

            foo.py__path__(sys_path)

        In case of a package, this returns Python's __path__ attribute, which
        is a list of paths (strings).
        Raises an AttributeError if the module is not a package.
        """
        if self.is_package:
            return self._py__path__
        else:
            raise AttributeError('Only packages have __path__ attributes.')

    def __repr__(self):
        return "<%s: %s@%s-%s is_stub=%s>" % (
            self.__class__.__name__, self._string_name,
            self.tree_node.start_pos[0], self.tree_node.end_pos[0],
            self._path is not None and self.is_stub()
        )
