from jedi.evaluate import compiled
from jedi.evaluate.filters import has_builtin_methods, \
    register_builtin_method, SpecialMethodFilter
from jedi.evaluate.base_context import ContextSet, Context


@has_builtin_methods
class CoroutineMixin(object):
    array_type = None

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        gen_obj = compiled.get_special_object(self.evaluator, 'COROUTINE_TYPE')
        yield SpecialMethodFilter(self, self.builtin_methods, gen_obj)
        for filter in gen_obj.get_filters(search_global):
            yield filter

    def py__bool__(self):
        return True

    def py__class__(self):
        gen_obj = compiled.get_special_object(self.evaluator, 'COROUTINE_TYPE')
        return gen_obj.py__class__()

    @property
    def name(self):
        return compiled.CompiledContextName(self, 'coroutine')


class Coroutine(CoroutineMixin, Context):
    def __init__(self, evaluator, func_execution_context):
        super(Coroutine, self).__init__(evaluator, parent_context=evaluator.builtins_module)
        self._func_execution_context = func_execution_context

    def execute_await(self):
        return self._func_execution_context.get_return_values()

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._func_execution_context)


@has_builtin_methods
class AsyncGeneratorMixin(object):
    array_type = None

    @register_builtin_method('__anext__')
    def py__anext__(self):
        return ContextSet.from_sets(lazy_context.infer() for lazy_context in self.py__aiter__())

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        gen_obj = compiled.get_special_object(self.evaluator, 'ASYNC_GENERATOR_TYPE')
        yield SpecialMethodFilter(self, self.builtin_methods, gen_obj)
        for filter in gen_obj.get_filters(search_global):
            yield filter

    def py__bool__(self):
        return True

    def py__class__(self):
        gen_obj = compiled.get_special_object(self.evaluator, 'ASYNC_GENERATOR_TYPE')
        return gen_obj.py__class__()

    @property
    def name(self):
        return compiled.CompiledContextName(self, 'asyncgenerator')


class AsyncGenerator(AsyncGeneratorMixin, Context):
    """Handling of `yield` functions."""
    def __init__(self, evaluator, func_execution_context):
        super(AsyncGenerator, self).__init__(evaluator, parent_context=evaluator.builtins_module)
        self._func_execution_context = func_execution_context

    def py__aiter__(self):
        return self._func_execution_context.get_yield_lazy_contexts(is_async=True)

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._func_execution_context)
