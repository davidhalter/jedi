import os
import re

from jedi._compatibility import FileNotFoundError
from jedi.plugins.base import BasePlugin
from jedi.evaluate.cache import evaluator_function_cache
from jedi.cache import memoize_method
from jedi.parser_utils import get_call_signature_for_any
from jedi.evaluate.base_context import ContextSet, iterator_to_context_set, \
    ContextWrapper
from jedi.evaluate.filters import AbstractTreeName, ParserTreeFilter, \
    TreeNameDefinition, NameWrapper, MergedFilter
from jedi.evaluate.context import ModuleContext, FunctionContext, \
    ClassContext
from jedi.evaluate.context.typing import TypingModuleFilterWrapper, \
    TypingModuleName
from jedi.evaluate.compiled import CompiledObject
from jedi.evaluate.compiled.context import CompiledName
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
                        # TODO use code_lines
                        stub_module_context = module_cls(
                            context_set, evaluator, stub_module_node,
                            path=path,
                            string_names=import_names,
                            code_lines=[],
                        )
                        modules = _merge_modules(context_set, stub_module_context)
                        return ContextSet.from_iterable(modules)
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
                if isinstance(actual_context, CompiledObject):
                    yield StubContextWithCompiled(stub_context, actual_context)
                elif isinstance(stub_context, FunctionContext) \
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


class NameWithStub(NameWithStubMixin, TreeNameDefinition):
    def __init__(self, parent_context, tree_name, stub_name):
        super(NameWithStub, self).__init__(parent_context, tree_name)
        self._stub_name = stub_name

    def _get_actual_contexts(self):
        # This is intentionally a subclass of NameWithStubMixin.
        return super(NameWithStubMixin, self).infer()


class CompiledNameWithStub(NameWithStubMixin, NameWrapper):
    def __init__(self, compiled_name, stub_name):
        super(CompiledNameWithStub, self).__init__(stub_name)
        self._compiled_name = compiled_name
        self._stub_name = stub_name

    def _get_actual_contexts(self):
        # This is intentionally a subclass of NameWithStubMixin.
        return self._compiled_name.infer()


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

    def values(self):
        used_stub_names = set()
        result_names = []
        for key_name, names in self._used_names.items():
            result_names += self._convert_names(self._filter(names))
            used_stub_names.add(key_name)

        non_stub_filters = []
        for f in self._non_stub_filters:
            # TODO this is really ugly. accessing some random _used_names and
            # _filters. Please change.
            if isinstance(f, MergedFilter):
                non_stub_filters += f._filters
            else:
                non_stub_filters.append(f)

        for non_stub_filter in non_stub_filters:
            if not hasattr(non_stub_filter, '_used_names'):
                continue
            for key_name in non_stub_filter._used_names:
                if key_name not in used_stub_names:
                    result_names += non_stub_filter.get(key_name)
        return result_names

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
                    if isinstance(non_stub_name, CompiledName):
                        yield CompiledNameWithStub(
                            non_stub_name,
                            n
                        )
                    else:
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
    def get_filters(self, search_global=False, until_position=None,
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
    def get_function_execution(self, arguments=None):
        return self.stub_context.get_function_execution(arguments)
        return super().get_function_execution(arguments, tree_node=self.stub_context.tree_node)


class StubOnlyModuleContext(ModuleContext):
    def __init__(self, non_stub_context_set, *args, **kwargs):
        super(StubOnlyModuleContext, self).__init__(*args, **kwargs)
        self.non_stub_context_set = non_stub_context_set

    def _get_first_non_stub_filters(self):
        for context in self.non_stub_context_set:
            yield next(context.get_filters(search_global=False))

    def get_filters(self, search_global=False, until_position=None,
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


class StubContextWithCompiled(ContextWrapper):
    def __init__(self, stub_context, compiled_context):
        super(StubContextWithCompiled, self).__init__(stub_context)
        self._compiled_context = compiled_context

    def py__doc__(self, include_call_signature=False):
        doc = self._compiled_context.py__doc__()
        if include_call_signature:
            call_sig = get_call_signature_for_any(self._wrapped_context.tree_node)
            if call_sig is not None:
                doc = call_sig + '\n\n' + doc
        return doc


class TypingModuleWrapper(StubOnlyModuleContext):
    def get_filters(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f
