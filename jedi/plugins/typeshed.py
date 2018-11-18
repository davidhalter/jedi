import os
import re

from jedi._compatibility import FileNotFoundError
from jedi.plugins.base import BasePlugin
from jedi.evaluate.cache import evaluator_function_cache
from jedi.cache import memoize_method
from jedi.parser_utils import get_call_signature_for_any, get_cached_code_lines
from jedi.evaluate.base_context import ContextSet, iterator_to_context_set, \
    ContextWrapper, NO_CONTEXTS
from jedi.evaluate.filters import ParserTreeFilter, \
    NameWrapper, AbstractFilter, TreeNameDefinition
from jedi.evaluate.context import ModuleContext, FunctionContext, \
    ClassContext
from jedi.evaluate.context.function import FunctionMixin
from jedi.evaluate.context.klass import ClassMixin
from jedi.evaluate.context.typing import TypingModuleFilterWrapper, \
    TypingModuleName
from jedi.evaluate.compiled.context import CompiledName, CompiledObject
from jedi.evaluate.utils import to_list


_jedi_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TYPESHED_PATH = os.path.join(_jedi_path, 'third_party', 'typeshed')


def _merge_create_stub_map(directories):
    map_ = {}
    for directory in directories:
        map_.update(_create_stub_map(directory))
    return map_


def _create_stub_map(directory):
    """
    Create a mapping of an importable name in Python to a stub file.
    """
    def generate():
        try:
            listed = os.listdir(directory)
        except (FileNotFoundError, OSError):
            # OSError is Python 2
            return

        for entry in listed:
            path = os.path.join(directory, entry)
            if os.path.isdir(path):
                init = os.path.join(path, '__init__.pyi')
                if os.path.isfile(init):
                    yield entry, init
            elif entry.endswith('.pyi') and os.path.isfile(path):
                name = entry.rstrip('.pyi')
                if name != '__init__':
                    yield name, path

    # Create a dictionary from the tuple generator.
    return dict(generate())


def _get_typeshed_directories(version_info):
    check_version_list = ['2and3', str(version_info.major)]
    for base in ['stdlib', 'third_party']:
        base = os.path.join(_TYPESHED_PATH, base)
        base_list = os.listdir(base)
        for base_list_entry in base_list:
            match = re.match(r'(\d+)\.(\d+)$', base_list_entry)
            if match is not None:
                if int(match.group(1)) == version_info.major \
                        and int(match.group(2)) <= version_info.minor:
                    check_version_list.append(base_list_entry)

        for check_version in check_version_list:
            yield os.path.join(base, check_version)


@evaluator_function_cache()
def _load_stub(evaluator, path):
    return evaluator.parse(path=path, cache=True)


def _merge_modules(context_set, stub_context):
    if not context_set:
        # If there are no results for normal modules, just
        # use a normal context for stub modules and don't
        # merge the actual module contexts with stubs.
        yield stub_context
        return

    for context in context_set:
        if isinstance(context, ModuleContext):
            yield StubModuleContext(
                context.evaluator,
                stub_context,
                context.tree_node,
                path=context._path,
                string_names=context._string_names,
                code_lines=context.code_lines
            )
        else:
            # TODO do we want this? This includes compiled?!
            yield stub_context


class TypeshedPlugin(BasePlugin):
    _version_cache = {}

    def _cache_stub_file_map(self, version_info):
        """
        Returns a map of an importable name in Python to a stub file.
        """
        # TODO this caches the stub files indefinitely, maybe use a time cache
        # for that?
        version = version_info[:2]
        try:
            return self._version_cache[version]
        except KeyError:
            pass

        self._version_cache[version] = file_set = \
            _merge_create_stub_map(_get_typeshed_directories(version_info))
        return file_set

    def import_module(self, callback):
        def wrapper(evaluator, import_names, parent_module_context, sys_path):
            if import_names == ('_sqlite3',):
                # TODO Maybe find a better solution for this?
                # The problem is IMO how star imports are priorized and that
                # there's no clear ordering.
                return NO_CONTEXTS

            # This is a huge exception, we follow a nested import
            # ``os.path``, because it's a very important one in Python
            # that is being achieved by messing with ``sys.modules`` in
            # ``os``.
            if import_names == ('os', 'path'):
                context_set = parent_module_context.py__getattribute__('path')
            else:
                context_set = callback(
                    evaluator,
                    import_names,
                    parent_module_context,
                    sys_path
                )
            import_name = import_names[-1]
            map_ = None
            if len(import_names) == 1:
                map_ = self._cache_stub_file_map(evaluator.grammar.version_info)
            elif isinstance(parent_module_context, StubModuleContext):
                path = parent_module_context.stub_context.py__path__()
                map_ = _merge_create_stub_map(path)

            if map_ is not None:
                path = map_.get(import_name)
                if path is not None:
                    try:
                        stub_module_node = _load_stub(evaluator, path)
                    except FileNotFoundError:
                        # The file has since been removed after looking for it.
                        # TODO maybe empty cache?
                        pass
                    else:
                        if import_names == ('typing',):
                            module_cls = TypingModuleWrapper
                        else:
                            module_cls = StubOnlyModuleContext
                        stub_module_context = module_cls(
                            context_set, evaluator, stub_module_node,
                            path=path,
                            string_names=import_names,
                            code_lines=get_cached_code_lines(evaluator.grammar, path),
                        )
                        modules = _merge_modules(context_set, stub_module_context)
                        return ContextSet(modules)
            # If no stub is found, just return the default.
            return context_set
        return wrapper


class NameWithStubMixin(object):
    """
    This name is only here to mix stub names with non-stub names. The idea is
    that the user can goto the actual name, but end up on the definition of the
    stub when inferring types.
    """
    @memoize_method
    @iterator_to_context_set
    def infer(self):
        actual_contexts = self._get_actual_contexts()
        stub_contexts = self._stub_name.infer()

        if not actual_contexts:
            for c in stub_contexts:
                yield c

        # This basically merges stub contexts with actual contexts.
        for actual_context in actual_contexts:
            for stub_context in stub_contexts:
                if isinstance(stub_context, FunctionContext) \
                        and isinstance(actual_context, FunctionContext):
                    yield StubFunctionContext.create_cached(
                        actual_context.evaluator,
                        self.parent_context,
                        actual_context,
                        stub_context,
                    )
                elif isinstance(stub_context, StubOnlyClass) \
                        and isinstance(actual_context, ClassContext):
                    yield StubClassContext.create_cached(
                        actual_context.evaluator,
                        self.parent_context,
                        actual_context,
                        stub_context,
                    )
                elif isinstance(stub_context, VersionInfo):
                    # TODO needed?
                    yield stub_context
                elif isinstance(actual_context, CompiledObject):
                    if stub_context.is_class():
                        yield CompiledStubClass.create_cached(
                            stub_context.evaluator, stub_context, actual_context)
                    elif stub_context.is_function():
                        yield CompiledStubFunction.create_cached(
                            stub_context.evaluator, stub_context, actual_context)
                    else:
                        yield stub_context
                else:
                    yield stub_context

            if not stub_contexts:
                yield actual_context


class VersionInfo(ContextWrapper):
    pass


class StubOnlyName(TreeNameDefinition):
    def infer(self):
        inferred = super(StubOnlyName, self).infer()
        if self.string_name == 'version_info' and self.get_root_context().py__name__() == 'sys':
            return [VersionInfo(c) for c in inferred]

        return [
            StubOnlyClass.create_cached(c.evaluator, c) if isinstance(c, ClassContext) else c
            for c in inferred
        ]


class StubName(NameWithStubMixin, NameWrapper):
    def __init__(self, parent_context, non_stub_name, stub_name):
        super(StubName, self).__init__(non_stub_name)
        self.parent_context = parent_context
        self._stub_name = stub_name

    def _get_actual_contexts(self):
        # This is intentionally a subclass of NameWithStubMixin.
        return self._wrapped_name.infer()


class CompiledNameWithStub(NameWithStubMixin, NameWrapper):
    # TODO do we actually need this class?
    def __init__(self, compiled_name, stub_name):
        super(CompiledNameWithStub, self).__init__(stub_name)
        self._compiled_name = compiled_name
        self._stub_name = stub_name

    def _get_actual_contexts(self):
        # This is intentionally a subclass of NameWithStubMixin.
        return self._compiled_name.infer()


class StubOnlyFilter(ParserTreeFilter):
    name_class = StubOnlyName

    def __init__(self, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubOnlyFilter, self).__init__(*args, **kwargs)

    def _is_name_reachable(self, name):
        if not super(StubOnlyFilter, self)._is_name_reachable(name):
            return False

        if not self._search_global:
            # Imports in stub files are only public if they have an "as"
            # export.
            definition = name.get_definition()
            if definition.type in ('import_from', 'import_name'):
                if name.parent.type not in ('import_as_name', 'dotted_as_name'):
                    return False
            n = name.value
            if n.startswith('_') and not (n.startswith('__') and n.endswith('__')):
                return False
        return True


class StubFilter(AbstractFilter):
    """
    Merging names from stubs and non-stubs.
    """
    def __init__(self, parent_context, non_stub_filters, stub_filters, add_non_stubs):
        self._parent_context = parent_context
        self._non_stub_filters = non_stub_filters
        self._stub_filters = stub_filters
        self._add_non_stubs = add_non_stubs

    def get(self, name):
        non_stub_names = self._get_names_from_filters(self._non_stub_filters, name)
        stub_names = self._get_names_from_filters(self._stub_filters, name)
        return self._merge_names(non_stub_names, stub_names)

    def values(self):
        name_dict = {}
        for non_stub_filter in self._non_stub_filters:
            for name in non_stub_filter.values():
                name_dict.setdefault(name.string_name, []).append(name)

        # Try to match the names of stubs with non-stubs. If there's no
        # match, just use the stub name. The user will be directed there
        # for all API accesses. Otherwise the user will be directed to the
        # non-stub positions (see StubName).
        for stub_filter in self._stub_filters:
            for stub_name in stub_filter.values():
                merged_names = self._merge_names(
                    names=name_dict.get(stub_name.string_name),
                    stub_names=[stub_name]
                )
                for merged_name in merged_names:
                    yield merged_name

    def _get_names_from_filters(self, filters, string_name):
        return [
            name
            for filter in filters
            for name in filter.get(string_name)
        ]

    @to_list
    def _merge_names(self, names, stub_names):
        if not stub_names:
            if self._add_non_stubs:
                return names
            return []
        if not names:
            if isinstance(self._stub_filters[0].context, TypingModuleWrapper):
                return [TypingModuleName(n) for n in stub_names]
            return stub_names

        result = []
        # The names are contained in both filters.
        for name in names:
            for stub_name in stub_names:
                if isinstance(self._stub_filters[0].context, TypingModuleWrapper):
                    stub_name = TypingModuleName(stub_name)

                if isinstance(name, CompiledName):
                    # TODO remove this?
                    result.append(CompiledNameWithStub(name, stub_name))
                else:
                    result.append(StubName(self._parent_context, name, stub_name))
        return result

    def __repr__(self):
        return '%s(%s, %s)' % (
            self.__class__.__name__,
            self._non_stub_filters,
            self._stub_filters,
        )


class _MixedStubContextMixin(object):
    """
    Mixes the actual contexts with the stub module contexts.
    """
    def __init__(self, evaluator, stub_context, *args, **kwargs):
        super(_MixedStubContextMixin, self).__init__(evaluator, *args, **kwargs)
        self.stub_context = stub_context


class _StubContextFilterMixin(object):
    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = self._wrapped_context.get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        yield self.stub_context.get_stub_only_filter(
            parent_context=self,
            # Take the first filter, which is here to filter module contents
            # and wrap it.
            non_stub_filters=[next(filters)],
            search_global=search_global,
            until_position=until_position,
            origin_scope=origin_scope,
        )
        for f in filters:
            yield f


class StubModuleContext(_MixedStubContextMixin, _StubContextFilterMixin, ModuleContext):
    @property
    def _wrapped_context(self):
        # TODO this is stupid.
        return super(_StubContextFilterMixin, self)


class StubClassContext(_StubContextFilterMixin, ClassMixin, ContextWrapper):
    def __init__(self, parent_context, cls, stub_context):
        super(StubClassContext, self).__init__(cls)
        self.parent_context = parent_context
        self.stub_context = stub_context

    def __getattribute__(self, name):
        if name in ('py__getitem__', 'py__simple_getitem__', 'py__bases__',
                    'execute_annotation', 'list_type_vars', 'define_generics'):
            # getitem is always done in the stub class.
            return getattr(self.stub_context, name)
        return super(StubClassContext, self).__getattribute__(name)


class StubFunctionContext(FunctionMixin, ContextWrapper):
    def __init__(self, parent_context, actual_context, stub_context):
        super(StubFunctionContext, self).__init__(actual_context)
        self.parent_context = parent_context
        self.stub_context = stub_context

    def get_function_execution(self, arguments=None):
        return self.stub_context.get_function_execution(arguments)


class _StubOnlyContextMixin(object):
    _add_non_stubs_in_filter = False

    def _get_stub_only_filters(self, **filter_kwargs):
        return [StubOnlyFilter(
            self.evaluator,
            context=self,
            **filter_kwargs
        )]

    def get_stub_only_filter(self, parent_context, non_stub_filters, **filter_kwargs):
        # Here we remap the names from stubs to the actual module. This is
        # important if type inferences is needed in that module.
        return StubFilter(
            parent_context,
            non_stub_filters,
            self._get_stub_only_filters(**filter_kwargs),
            add_non_stubs=self._add_non_stubs_in_filter,
        )

    def _get_base_filters(self, filters, search_global=False,
                          until_position=None, origin_scope=None):
        next(filters)  # Ignore the first filter and replace it with our own
        yield self.get_stub_only_filter(
            parent_context=self,
            non_stub_filters=list(self._get_first_non_stub_filters()),
            search_global=search_global,
            until_position=until_position,
            origin_scope=origin_scope,
        )

        for f in filters:
            yield f


class StubOnlyModuleContext(_StubOnlyContextMixin, ModuleContext):
    _add_non_stubs_in_filter = True

    def __init__(self, non_stub_context_set, *args, **kwargs):
        super(StubOnlyModuleContext, self).__init__(*args, **kwargs)
        self.non_stub_context_set = non_stub_context_set

    def _get_first_non_stub_filters(self):
        for context in self.non_stub_context_set:
            yield next(context.get_filters(search_global=False))

    def _get_stub_only_filters(self, search_global, **filter_kwargs):
        stub_filters = super(StubOnlyModuleContext, self)._get_stub_only_filters(
            search_global=search_global, **filter_kwargs
        )
        stub_filters += self.iter_star_filters(search_global=search_global)
        return stub_filters

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(StubOnlyModuleContext, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        for f in self._get_base_filters(filters, search_global, until_position, origin_scope):
            yield f


class StubOnlyClass(_StubOnlyContextMixin, ClassMixin, ContextWrapper):
    pass


class _CompiledStubContext(ContextWrapper):
    def __init__(self, stub_context, compiled_context):
        super(_CompiledStubContext, self).__init__(stub_context)
        self._compiled_context = compiled_context

    def py__doc__(self, include_call_signature=False):
        doc = self._compiled_context.py__doc__()
        if include_call_signature:
            call_sig = get_call_signature_for_any(self._wrapped_context.tree_node)
            if call_sig is not None:
                doc = call_sig + '\n\n' + doc
        return doc


class CompiledStubFunction(_CompiledStubContext):
    pass


class CompiledStubClass(_StubOnlyContextMixin, _CompiledStubContext, ClassMixin):
    def _get_first_non_stub_filters(self):
        yield next(self._compiled_context.get_filters(search_global=False))

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = self._wrapped_context.get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        for f in self._get_base_filters(filters, search_global, until_position, origin_scope):
            yield f


class TypingModuleWrapper(StubOnlyModuleContext):
    # TODO should use this instead of the isinstance check
    def get_filterss(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f
