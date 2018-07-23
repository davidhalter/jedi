from jedi.plugins.base import BasePlugin
from jedi.evaluate.base_context import Context, ContextSet


class TypeshedPlugin(BasePlugin):
    def foo():
        return


class TypeshedProxy(object):
    def __init__(self, parent_context, context, typeshed_context):
        self.parent_context = parent_context
        self._context = context
        self._typeshed_context = typeshed_context

    # We have to overwrite everything that has to do with trailers, name
    # lookups and filters to make it possible to route name lookups towards
    # compiled objects and the rest towards tree node contexts.
    def py__getattribute__(self, *args, **kwargs):
        context_results = self._context.py__getattribute__(
            *args, **kwargs
        )
        typeshed_results = self._typeshed_context = py__getattribute__(
            *args, **kwargs
        )
        print(context_results, typeshed_results)
        return context_results

    def __getattr__(self, name):
        return getattr(self._context, name)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.access_handle.get_repr())
