import os
import re

from jedi._compatibility import FileNotFoundError
from jedi.plugins.base import BasePlugin
from jedi.evaluate.cache import evaluator_as_method_param_cache
from jedi.evaluate.base_context import Context, ContextSet
from jedi.evaluate.context import ModuleContext


_TYPESHED_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'third_party',
    'typeshed',
)


def _create_stub_map(directory):
    """
    Create a mapping of an importable name in Python to a stub file.
    """
    def generate():
        try:
            listed = os.listdir(directory)
        except FileNotFoundError:
            return

        for entry in listed:
            path = os.path.join(directory, entry)
            if os.path.isdir(path):
                init = os.path.join(path, '__init__.pyi')
                if os.path.isfile(init):
                    yield entry, init
            elif entry.endswith('.pyi') and os.path.isfile(path):
                name = entry.rstrip('.pyi')
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

        self._version_cache[version] = file_set = {}
        for dir_ in _get_typeshed_directories(version_info):
            file_set.update(_create_stub_map(dir_))

        return file_set

    @evaluator_as_method_param_cache()
    def _load_stub(self, evaluator, path):
        return evaluator.parse(path=path, cache=True)

    def import_module(self, callback):
        def wrapper(evaluator, import_names, module_context, sys_path):
            # This is a huge exception, we follow a nested import
            # ``os.path``, because it's a very important one in Python
            # that is being achieved by messing with ``sys.modules`` in
            # ``os``.
            mapped = self._cache_stub_file_map(evaluator.grammar.version_info)
            context_set = callback(evaluator, import_names, module_context, sys_path)
            if len(import_names) == 1:
                path = mapped.get(import_names[0])
                if path is not None:
                    try:
                        stub_module = self._load_stub(evaluator, path)
                    except FileNotFoundError:
                        # The file has since been removed after looking for it.
                        # TODO maybe empty cache?
                        pass
                    else:
                        return ContextSet.from_iterable(
                            StubProxy(
                                context.parent_context,
                                context,
                                ModuleContext(evaluator, stub_module, path, code_lines=[])
                            ) for context in context_set
                        )
            return context_set
        return wrapper


class StubProxy(object):
    def __init__(self, parent_context, context, stub_context):
        self.parent_context = parent_context
        self._context = context
        self._stub_context = stub_context

    # We have to overwrite everything that has to do with trailers, name
    # lookups and filters to make it possible to route name lookups towards
    # compiled objects and the rest towards tree node contexts.
    def py__getattribute__(self, *args, **kwargs):
        context_results = self._context.py__getattribute__(
            *args, **kwargs
        )
        typeshed_results = self._stub_context.py__getattribute__(
            *args, **kwargs
        )
        return context_results

    def __getattr__(self, name):
        return getattr(self._context, name)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.access_handle.get_repr())
