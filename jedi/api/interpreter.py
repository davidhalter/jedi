"""
TODO Some parts of this module are still not well documented.
"""

from jedi.inference.context import ModuleContext
from jedi.inference import compiled
from jedi.inference.compiled import mixed
from jedi.inference.compiled.access import create_access_path
from jedi.inference.base_context import ContextWrapper


def _create(infer_state, obj):
    return compiled.create_from_access_path(
        infer_state, create_access_path(infer_state, obj)
    )


class NamespaceObject(object):
    def __init__(self, dct):
        self.__dict__ = dct


class MixedModuleContext(ContextWrapper):
    type = 'mixed_module'

    def __init__(self, infer_state, tree_module, namespaces, file_io, code_lines):
        module_context = ModuleContext(
            infer_state, tree_module,
            file_io=file_io,
            string_names=('__main__',),
            code_lines=code_lines
        )
        super(MixedModuleContext, self).__init__(module_context)
        self._namespace_objects = [NamespaceObject(n) for n in namespaces]

    def get_filters(self, *args, **kwargs):
        for filter in self._wrapped_context.get_filters(*args, **kwargs):
            yield filter

        for namespace_obj in self._namespace_objects:
            compiled_object = _create(self.infer_state, namespace_obj)
            mixed_object = mixed.MixedObject(
                compiled_object=compiled_object,
                tree_context=self._wrapped_context
            )
            for filter in mixed_object.get_filters(*args, **kwargs):
                yield filter
