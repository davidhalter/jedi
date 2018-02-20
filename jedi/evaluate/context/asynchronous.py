from jedi.evaluate.filters import publish_method, BuiltinOverwrite
from jedi.evaluate.base_context import ContextSet


class AsyncBase(BuiltinOverwrite):
    def __init__(self, evaluator, func_execution_context):
        super(AsyncBase, self).__init__(evaluator)
        self._func_execution_context = func_execution_context

    @property
    def name(self):
        return self.get_builtin_object().py__name__()

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._func_execution_context)


class Coroutine(AsyncBase):
    special_object_identifier = u'COROUTINE_TYPE'

    @publish_method('__await__')
    def _await(self):
        return self._func_execution_context.get_return_values()


class AsyncGenerator(AsyncBase):
    """Handling of `yield` functions."""
    special_object_identifier = u'ASYNC_GENERATOR_TYPE'

    @publish_method('__anext__')
    def py__anext__(self):
        return ContextSet.from_sets(lazy_context.infer() for lazy_context in self.py__aiter__())

    def py__aiter__(self):
        return self._func_execution_context.get_yield_lazy_contexts(is_async=True)
