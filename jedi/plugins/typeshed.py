import os
import re
from pkg_resources import resource_filename

from jedi._compatibility import FileNotFoundError
from jedi.plugins.base import BasePlugin
from jedi.evaluate.cache import evaluator_function_cache
from jedi.cache import memoize_method
from jedi.evaluate.base_context import ContextSet, iterator_to_context_set
from jedi.evaluate.filters import AbstractTreeName, ParserTreeFilter, \
    TreeNameDefinition
from jedi.evaluate.context import ModuleContext, FunctionContext, \
    ClassContext, BoundMethod
from jedi.evaluate.context.typing import TypingModuleFilterWrapper, \
    TypingModuleName
from jedi.evaluate.compiled import CompiledObject
from jedi.evaluate.utils import to_list


_TYPESHED_PATH = resource_filename('jedi', os.path.join('third_party', 'typeshed'))


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
        # TODO what about compiled?
        if isinstance(context, ModuleContext):
            yield StubModuleContext(
                context.evaluator,
                stub_context,
                context.tree_node,
                context._path,
                context.code_lines
            )
        else:
            # TODO do we want this?
            yield context


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
            # This is a huge exception, we follow a nested import
            # ``os.path``, because it's a very important one in Python
            # that is being achieved by messing with ``sys.modules`` in
            # ``os``.
            context_set = callback(
                evaluator,
                import_names,
                parent_module_context,
                sys_path
            )
            # Don't use CompiledObjects, they are just annoying and don't
            # really help with anything. Just use the stub files instead.
            context_set = ContextSet.from_iterable(
                c for c in context_set if not isinstance(c, CompiledObject)
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
                        # TODO use code_lines
                        stub_module_context = module_cls(
                            context_set, evaluator, stub_module_node, path, code_lines=[]
                        )
                        modules = _merge_modules(context_set, stub_module_context)
                        return ContextSet.from_iterable(modules)
            # If no stub is found, just return the default.
            return context_set
        return wrapper


class NameWithStub(TreeNameDefinition):
    """
    This name is only here to mix stub names with non-stub names. The idea is
    that the user can goto the actual name, but end up on the definition of the
    stub when inferring types.
    """

    def __init__(self, parent_context, tree_name, stub_name):
        super(NameWithStub, self).__init__(parent_context, tree_name)
        self._stub_name = stub_name

    @memoize_method
    @iterator_to_context_set
    def infer(self):
        actual_contexts = super(NameWithStub, self).infer()
        stub_contexts = self._stub_name.infer()

        if not actual_contexts:
            for c in stub_contexts:
                yield c

        # This basically merges stub contexts with actual contexts.
        for actual_context in actual_contexts:
            for stub_context in stub_contexts:
                if isinstance(stub_context, FunctionContext) \
                        and isinstance(actual_context, FunctionContext):
                    yield StubFunctionContext(
                        actual_context.evaluator,
                        stub_context,
                        actual_context.parent_context,
                        actual_context.tree_node,
                    )
                elif isinstance(stub_context, ClassContext) \
                        and isinstance(actual_context, ClassContext):
                    yield StubClassContext(
                        actual_context.evaluator,
                        stub_context,
                        actual_context.parent_context,
                        actual_context.tree_node,
                    )
                else:
                    yield stub_context

            if not stub_contexts:
                yield actual_context


class StubParserTreeFilter(ParserTreeFilter):
    name_class = NameWithStub

    def __init__(self, non_stub_filters, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubParserTreeFilter, self).__init__(*args, **kwargs)
        self._non_stub_filters = non_stub_filters

    def get(self, name):
        try:
            names = self._used_names[name]
        except KeyError:
            return self._get_non_stub_names(name)

        return self._convert_names(self._filter(names))

    # TODO maybe implement values, because currently the names that don't exist
    # in the stub file are not part of values.

    def _check_flows(self, names):
        return names

    def _get_non_stub_names(self, string_name):
        return [
            name
            for non_stub_filter in self._non_stub_filters
            for name in non_stub_filter.get(string_name)
        ]

    @to_list
    def _convert_names(self, names):
        for name in names:
            non_stub_names = self._get_non_stub_names(name.value)
            # Try to match the names of stubs with non-stubs. If there's no
            # match, just use the stub name. The user will be directed there
            # for all API accesses. Otherwise the user will be directed to the
            # non-stub positions (see NameWithStub).
            n = TreeNameDefinition(self.context, name)
            if isinstance(self.context, TypingModuleWrapper):
                n = TypingModuleName(n)
            if len(non_stub_names):
                for non_stub_name in non_stub_names:
                    assert isinstance(non_stub_name, AbstractTreeName), non_stub_name
                    yield self.name_class(
                        non_stub_name.parent_context,
                        non_stub_name.tree_name,
                        stub_name=n,
                    )
            else:
                yield n

    def _is_name_reachable(self, name):
        if not super(StubParserTreeFilter, self)._is_name_reachable(name):
            return False

        if not self._search_global:
            # Imports in stub files are only public if they have an "as"
            # export.
            definition = name.get_definition()
            if definition.type in ('import_from', 'import_name'):
                if name.parent.type not in ('import_as_name', 'dotted_as_name'):
                    return False
        return True


class _MixedStubContextMixin(object):
    """
    Mixes the actual contexts with the stub module contexts.
    """
    def __init__(self, evaluator, stub_context, *args, **kwargs):
        super(_MixedStubContextMixin, self).__init__(evaluator, *args, **kwargs)
        self.stub_context = stub_context


class _StubContextFilterMixin(_MixedStubContextMixin):
    def get_filters(self, search_global, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(_StubContextFilterMixin, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        yield StubParserTreeFilter(
            # Take the first filter, which is here to filter module contents
            # and wrap it.
            [next(filters)],
            self.evaluator,
            context=self.stub_context,
            until_position=until_position,
            origin_scope=origin_scope,
            search_global=search_global,
        )
        for f in filters:
            yield f


class StubModuleContext(_StubContextFilterMixin, ModuleContext):
    pass


class StubClassContext(_StubContextFilterMixin, ClassContext):
    def __getattribute__(self, name):
        if name in ('py__getitem__', 'py__simple_getitem__', 'py__bases__',
                    'execute_annotation'):
            # getitem is always done in the stub class.
            return getattr(self.stub_context, name)
        return super(StubClassContext, self).__getattribute__(name)


class StubFunctionContext(_MixedStubContextMixin, FunctionContext):
    def get_function_execution(self, arguments):
        return self.stub_context.get_function_execution(arguments)
        return super().get_function_execution(arguments, tree_node=self.stub_context.tree_node)


class StubOnlyModuleContext(ModuleContext):
    def __init__(self, non_stub_context_set, *args, **kwargs):
        super(StubOnlyModuleContext, self).__init__(*args, **kwargs)
        self._non_stub_context_set = non_stub_context_set

    def _get_first_non_stub_filters(self):
        for context in self._non_stub_context_set:
            yield next(context.get_filters(search_global=False))

    def get_filters(self, search_global, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(StubOnlyModuleContext, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        next(filters)  # Ignore the first filter and replace it with our own

        # Here we remap the names from stubs to the actual module. This is
        # important if type inferences is needed in that module.
        yield StubParserTreeFilter(
            list(self._get_first_non_stub_filters()),
            self.evaluator,
            context=self,
            until_position=until_position,
            origin_scope=origin_scope,
            search_global=search_global,
        )
        for f in filters:
            yield f


class TypingModuleWrapper(StubOnlyModuleContext):
    def get_filters(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f
