"""
TODO Some parts of this module are still not well documented.
"""

from jedi.inference import compiled
from jedi.inference.filters import ParserTreeFilter, MergedFilter
from jedi.inference.compiled import mixed
from jedi.inference.compiled.access import create_access_path
from jedi.inference.context import ModuleContext


def _create(inference_state, obj):
    return compiled.create_from_access_path(
        inference_state, create_access_path(inference_state, obj)
    )


class NamespaceObject(object):
    def __init__(self, dct):
        self.__dict__ = dct


class MixedModuleContext(ModuleContext):
    def __init__(self, tree_module_value, namespaces):
        super(MixedModuleContext, self).__init__(tree_module_value)
        self._namespace_objects = [NamespaceObject(n) for n in namespaces]

    def _get_mixed_object(self, compiled_value):
        return mixed.MixedObject(
            compiled_value=compiled_value,
            tree_value=self._value
        )

    def get_filters(self, until_position=None, origin_scope=None):
        yield MergedFilter(
            ParserTreeFilter(
                parent_context=self,
                until_position=until_position,
                origin_scope=origin_scope
            ),
            self.get_global_filter(),
        )

        for namespace_obj in self._namespace_objects:
            compiled_value = _create(self.inference_state, namespace_obj)
            mixed_object = self._get_mixed_object(compiled_value)
            for filter in mixed_object.get_filters(until_position, origin_scope):
                yield filter
