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
from jedi.evaluate.context import ModuleContext, FunctionContext, ClassContext
from jedi.evaluate.syntax_tree import tree_name_to_contexts
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
            yield ModuleStubContext(
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
                parent_module_context.actual_context  # noqa
                    if isinstance(parent_module_context, ModuleStubContext)
                    else parent_module_context,
                sys_path
            )
            import_name = import_names[-1]
            map_ = None
            if len(import_names) == 1 and import_name != 'typing':
                map_ = self._cache_stub_file_map(evaluator.grammar.version_info)
            elif isinstance(parent_module_context, ModuleStubContext):
                map_ = _merge_create_stub_map(parent_module_context.py__path__())

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
                        # TODO use code_lines
                        stub_module_context = ModuleContext(
                            evaluator, stub_module_node, path, code_lines=[]
                        )
                        return ContextSet.from_iterable(
                            _merge_modules(context_set, stub_module_context)
                        )
            # If no stub is found, just return the default.
            return context_set
        return wrapper


class StubName(TreeNameDefinition):
    """
    This name is only here to mix stub names with non-stub names. The idea is
    that the user can goto the actual name, but end up on the definition of the
    stub when inferring types.
    """

    def __init__(self, parent_context, tree_name, stub_parent_context, stub_tree_name):
        super(StubName, self).__init__(parent_context, tree_name)
        self._stub_parent_context = stub_parent_context
        self._stub_tree_name = stub_tree_name

    @memoize_method
    @iterator_to_context_set
    def infer(self):
        actual_contexts = super(StubName, self).infer()
        stub_contexts = tree_name_to_contexts(
            self.parent_context.evaluator,
            self._stub_parent_context,
            self._stub_tree_name
        )

        if not actual_contexts:
            for c in stub_contexts:
                yield c

        for actual_context in actual_contexts:
            for stub_context in stub_contexts:
                if isinstance(stub_context, FunctionContext) \
                        and isinstance(actual_context, FunctionContext):
                    yield FunctionStubContext(
                        actual_context.evaluator,
                        stub_context,
                        actual_context.parent_context,
                        actual_context.tree_node,
                    )
                elif isinstance(stub_context, ClassContext) \
                        and isinstance(actual_context, ClassContext):
                    yield ClassStubContext(
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
    name_class = StubName

    def __init__(self, non_stub_filter, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubParserTreeFilter, self).__init__(*args, **kwargs)
        self._non_stub_filter = non_stub_filter

    def _check_flows(self, names):
        return names

    @to_list
    def _convert_names(self, names):
        for name in names:
            found_actual_names = self._non_stub_filter.get(name.value)
            # Try to match the names of stubs with non-stubs. If there's no
            # match, just use the stub name. The user will be directed there
            # for all API accesses. Otherwise the user will be directed to the
            # non-stub positions (see StubName).
            if not len(found_actual_names):
                yield TreeNameDefinition(self.context, name)
            else:
                for non_stub_name in found_actual_names:
                    assert isinstance(non_stub_name, AbstractTreeName), non_stub_name
                    yield self.name_class(
                        non_stub_name.parent_context,
                        non_stub_name.tree_name,
                        self.context,
                        name,
                    )

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
            next(filters),
            self.evaluator,
            context=self.stub_context,
            until_position=until_position,
            origin_scope=origin_scope,
            search_global=search_global,
        )
        for f in filters:
            yield f


class ModuleStubContext(_StubContextFilterMixin, ModuleContext):
    pass


class ClassStubContext(_StubContextFilterMixin, ClassContext):
    pass


class FunctionStubContext(_MixedStubContextMixin, FunctionContext):
    def py__call__(self, arguments):
        return self.stub_context.py__call__(arguments)
