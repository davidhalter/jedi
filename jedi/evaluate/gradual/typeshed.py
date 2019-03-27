import os
import re

from jedi._compatibility import FileNotFoundError
from jedi.parser_utils import get_cached_code_lines
from jedi.evaluate.cache import evaluator_function_cache
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
from jedi.evaluate.context import ModuleContext
from jedi.evaluate.gradual.stub_context import StubModuleContext, \
    TypingModuleWrapper, StubOnlyModuleContext

_jedi_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    return evaluator.parse(path=path, cache=True, use_latest_grammar=True)


def _merge_modules(context_set, stub_context):
    if not context_set:
        # If there are no results for normal modules, just
        # use a normal context for stub modules and don't
        # merge the actual module contexts with stubs.
        yield stub_context
        return

    for context in context_set:
        if isinstance(context, ModuleContext):
            yield StubModuleContext.create_cached(context.evaluator, context, stub_context)
        else:
            # TODO do we want this? This includes compiled?!
            yield stub_context


_version_cache = {}


def _cache_stub_file_map(version_info):
    """
    Returns a map of an importable name in Python to a stub file.
    """
    # TODO this caches the stub files indefinitely, maybe use a time cache
    # for that?
    version = version_info[:2]
    try:
        return _version_cache[version]
    except KeyError:
        pass

    _version_cache[version] = file_set = \
        _merge_create_stub_map(_get_typeshed_directories(version_info))
    return file_set


def import_module_decorator(func):
    def wrapper(evaluator, import_names, parent_module_context, sys_path):
        if import_names == ('_sqlite3',):
            # TODO Maybe find a better solution for this?
            # The problem is IMO how star imports are priorized and that
            # there's no clear ordering.
            return NO_CONTEXTS

        if import_names == ('os', 'path'):
            # This is a huge exception, we follow a nested import
            # ``os.path``, because it's a very important one in Python
            # that is being achieved by messing with ``sys.modules`` in
            # ``os``.
            if parent_module_context is None:
                parent_module_context, = evaluator.import_module(('os',))
            return parent_module_context.py__getattribute__('path')

        from jedi.evaluate.imports import JediImportError
        try:
            context_set = func(
                evaluator,
                import_names,
                parent_module_context,
                sys_path
            )
        except JediImportError:
            if import_names == ('typing',):
                # TODO this is also quite ugly, please refactor.
                context_set = NO_CONTEXTS
            else:
                raise

        import_name = import_names[-1]
        map_ = None
        if len(import_names) == 1:
            map_ = _cache_stub_file_map(evaluator.grammar.version_info)
        elif isinstance(parent_module_context, StubModuleContext):
            if not parent_module_context.stub_context.is_package():
                # Only if it's a package (= a folder) something can be
                # imported.
                return context_set
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
                        # The code was loaded with latest_grammar, so use
                        # that.
                        code_lines=get_cached_code_lines(evaluator.latest_grammar, path),
                    )
                    modules = _merge_modules(context_set, stub_module_context)
                    return ContextSet(modules)
        # If no stub is found, just return the default.
        return context_set
    return wrapper
