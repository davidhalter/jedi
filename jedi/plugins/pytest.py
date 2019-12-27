from jedi._compatibility import FileNotFoundError
from jedi.inference.cache import inference_state_method_cache
from jedi.inference.imports import load_module_from_path
from jedi.inference.filters import ParserTreeFilter
from jedi.inference.base_value import NO_VALUES, ValueSet


def execute(callback):
    def wrapper(value, arguments):
        if value.py__name__() == 'fixture' \
                and value.parent_context.py__name__() == '_pytest.fixtures':
            return NO_VALUES

        return callback(value, arguments)
    return wrapper


def infer_anonymous_param(func):
    def get_returns(value):
        if value.tree_node.annotation is not None:
            return value.execute_with_values()

        # In pytest we need to differentiate between generators and normal
        # returns.
        # Parameters still need to be anonymous, .as_context() ensures that.
        function_context = value.as_context()
        if function_context.is_generator():
            return function_context.merge_yield_values()
        else:
            return function_context.get_return_values()

    def wrapper(param):
        module = param.get_root_context()
        fixtures = _goto_pytest_fixture(module, param.string_name)
        if fixtures:
            return ValueSet.from_sets(
                get_returns(value)
                for fixture in fixtures
                for value in fixture.infer()
            )
        return func(param)
    return wrapper


def _goto_pytest_fixture(module_context, name):
    for module_context in _iter_pytest_modules(module_context):
        names = FixtureFilter(module_context).get(name)
        if names:
            return names


@inference_state_method_cache()
def _iter_pytest_modules(module_context):
    yield module_context

    folder = module_context.get_value().file_io.get_parent_folder()
    sys_path = module_context.inference_state.get_sys_path()
    while any(folder.path.startswith(p) for p in sys_path):
        file_io = folder.get_file_io('conftest.py')
        try:
            m = load_module_from_path(module_context.inference_state, file_io)
            yield m.as_context()
        except FileNotFoundError:
            pass
        folder = folder.get_parent_folder()


class FixtureFilter(ParserTreeFilter):
    def _filter(self, names):
        for name in super(FixtureFilter, self)._filter(names):
            if name.parent.type == 'funcdef':
                # Class fixtures are not supported
                yield name
