import os

from jedi.evaluate.base_context import ContextWrapper, ContextSet, \
    NO_CONTEXTS
from jedi.evaluate.context.klass import ClassMixin, ClassContext
from jedi.evaluate.context.module import ModuleContext
from jedi.evaluate.filters import ParserTreeFilter, \
    TreeNameDefinition
from jedi.evaluate.utils import to_list
from jedi.evaluate.gradual.typing import TypingModuleFilterWrapper


class _StubContextMixin(object):
    def is_stub(self):
        return True


class StubModuleContext(_StubContextMixin, ModuleContext):
    def __init__(self, non_stub_context_set, *args, **kwargs):
        super(StubModuleContext, self).__init__(*args, **kwargs)
        self.non_stub_context_set = non_stub_context_set

    def sub_modules_dict(self):
        """
        We have to overwrite this, because it's possible to have stubs that
        don't have code for all the child modules. At the time of writing this
        there are for example no stubs for `json.tool`.
        """
        names = {}
        for context in self.non_stub_context_set:
            try:
                method = context.sub_modules_dict
            except AttributeError:
                pass
            else:
                names.update(method())
        names.update(super(StubModuleContext, self).sub_modules_dict())
        return names

    def _get_first_non_stub_filters(self):
        for context in self.non_stub_context_set:
            yield next(context.get_filters(search_global=False))

    def _get_stub_filters(self, search_global, **filter_kwargs):
        return [StubFilter(
            self.evaluator,
            context=self,
            search_global=search_global,
            **filter_kwargs
        )] + list(self.iter_star_filters(search_global=search_global))

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(StubModuleContext, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        next(filters)  # Ignore the first filter and replace it with our own
        stub_filters = self._get_stub_filters(
            search_global=search_global,
            until_position=until_position,
            origin_scope=origin_scope,
        )
        for f in stub_filters:
            yield f

        for f in filters:
            yield f

    def _iter_module_names(self, paths):
        for path in paths:
            dirs = os.listdir(path)
            for name in dirs:
                if os.path.isdir(os.path.join(path, name)):
                    if name != '__pycache__':
                        yield name
                if name.endswith('.pyi'):
                    if name != '__init__.pyi':
                        yield name[:-4]


class StubClass(_StubContextMixin, ClassMixin, ContextWrapper):
    pass


class TypingModuleWrapper(StubModuleContext):
    def get_filters(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f


def stub_to_actual_context_set(stub_context, ignore_compiled=False):
    stub_module = stub_context.get_root_context()
    if not stub_module.is_stub():
        return ContextSet([stub_context])

    qualified_names = stub_context.get_qualified_names()
    return _infer_from_stub(stub_module, qualified_names, ignore_compiled)


def _infer_from_stub(stub_module, qualified_names, ignore_compiled):
    if qualified_names is None:
        return NO_CONTEXTS

    assert isinstance(stub_module, StubModuleContext), stub_module
    non_stubs = stub_module.non_stub_context_set
    if ignore_compiled:
        non_stubs = non_stubs.filter(lambda c: not c.is_compiled())
    for name in qualified_names:
        non_stubs = non_stubs.py__getattribute__(name)
    return non_stubs


def try_stubs_to_actual_context_set(stub_contexts, prefer_stub_to_compiled=False):
    return ContextSet.from_sets(
        stub_to_actual_context_set(stub_context, ignore_compiled=prefer_stub_to_compiled)
        or ContextSet([stub_context])
        for stub_context in stub_contexts
    )


@to_list
def try_stub_to_actual_names(names, prefer_stub_to_compiled=False):
    for name in names:
        module = name.get_root_context()
        if not module.is_stub():
            yield name
            continue

        name_list = name.get_qualified_names()
        if name_list is None:
            contexts = NO_CONTEXTS
        else:
            contexts = _infer_from_stub(
                module,
                name_list[:-1],
                ignore_compiled=prefer_stub_to_compiled,
            )
        if contexts:
            if name_list:
                for new_name in contexts.py__getattribute__(name_list[-1], is_goto=True):
                    yield new_name
            else:
                for c in contexts:
                    yield c.name
        else:
            yield name


def _load_stub_module(module):
    if module.is_stub():
        return module
    from jedi.evaluate.gradual.typeshed import _try_to_load_stub
    return _try_to_load_stub(
        module.evaluator,
        ContextSet([module]),
        parent_module_context=None,
        import_names=module.string_names
    )


def name_to_stub(name):
    return ContextSet.from_sets(to_stub(c) for c in name.infer())


def to_stub(context):
    if context.is_stub():
        return ContextSet([context])

    qualified_names = context.get_qualified_names()
    stub_module = _load_stub_module(context.get_root_context())
    if stub_module is None or qualified_names is None:
        return NO_CONTEXTS

    stub_contexts = ContextSet([stub_module])
    for name in qualified_names:
        stub_contexts = stub_contexts.py__getattribute__(name)
    return stub_contexts


class _StubName(TreeNameDefinition):
    def infer(self):
        inferred = super(_StubName, self).infer()
        if self.string_name == 'version_info' and self.get_root_context().py__name__() == 'sys':
            return [VersionInfo(c) for c in inferred]

        return [
            StubClass.create_cached(c.evaluator, c) if isinstance(c, ClassContext) else c
            for c in inferred
        ]


class StubFilter(ParserTreeFilter):
    name_class = _StubName

    def __init__(self, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubFilter, self).__init__(*args, **kwargs)

    def _is_name_reachable(self, name):
        if not super(StubFilter, self)._is_name_reachable(name):
            return False

        if not self._search_global:
            # Imports in stub files are only public if they have an "as"
            # export.
            definition = name.get_definition()
            if definition.type in ('import_from', 'import_name'):
                if name.parent.type not in ('import_as_name', 'dotted_as_name'):
                    return False
            n = name.value
            if n.startswith('_') and not (n.startswith('__') and n.endswith('__')):
                return False
        return True


class VersionInfo(ContextWrapper):
    pass
