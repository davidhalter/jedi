import os
import re
from pkg_resources import resource_filename

from jedi._compatibility import FileNotFoundError
from jedi.plugins.base import BasePlugin
from jedi.evaluate.cache import evaluator_function_cache
from jedi.evaluate.base_context import Context, ContextSet, NO_CONTEXTS
from jedi.evaluate.context import ModuleContext


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
                    if isinstance(parent_module_context, ModuleStubProxy)
                    else parent_module_context,
                sys_path
            )
            import_name = import_names[-1]
            map_ = None
            if len(import_names) == 1 and import_name != 'typing':
                map_ = self._cache_stub_file_map(evaluator.grammar.version_info)
            elif isinstance(parent_module_context, ModuleStubProxy):
                map_ = _merge_create_stub_map(parent_module_context.py__path__())

            if map_ is not None:
                path = map_.get(import_name)
                if path is not None:
                    try:
                        stub_module = _load_stub(evaluator, path)
                    except FileNotFoundError:
                        # The file has since been removed after looking for it.
                        # TODO maybe empty cache?
                        pass
                    else:
                        return ContextSet.from_iterable(
                            ModuleStubProxy(
                                parent_module_context,
                                ModuleContext(evaluator, stub_module, path, code_lines=[]),
                                context,
                            ) for context in context_set
                        )
            # If no stub is found, just return the default.
            return context_set
        return wrapper


class StubProxy(object):
    def __init__(self, stub_context):
        self._stub_context = stub_context

    # We have to overwrite everything that has to do with trailers, name
    # lookups and filters to make it possible to route name lookups towards
    # compiled objects and the rest towards tree node contexts.
    def py__getattribute__(self, *args, **kwargs):
        #context_results = self._context.py__getattribute__(
        #    *args, **kwargs
        #)
        typeshed_results = list(self._stub_context.py__getattribute__(
            *args, **kwargs
        ))
        if not typeshed_results:
            return NO_CONTEXTS

        return ContextSet.from_iterable(
            StubProxy(c) for c in typeshed_results
        )

    def __getattr__(self, name):
        return getattr(self._stub_context, name)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self._stub_context)


class ModuleStubProxy(StubProxy):
    def __init__(self, parent_module_context, stub_context, actual_context):
        super(ModuleStubProxy, self).__init__(stub_context)
        self._parent_module_context = parent_module_context
        self.actual_context = actual_context
