import os

from jedi.cache import memoize_method
from jedi.parser_utils import get_call_signature_for_any
from jedi.evaluate.base_context import ContextWrapper, ContextSet, \
    NO_CONTEXTS, iterator_to_context_set
from jedi.evaluate.context.klass import ClassMixin, ClassContext
from jedi.evaluate.context.module import ModuleContext
from jedi.evaluate.filters import ParserTreeFilter, \
    NameWrapper, TreeNameDefinition
from jedi.evaluate.utils import to_list
from jedi.evaluate.gradual.typing import TypingModuleFilterWrapper, AnnotatedClass


class _StubOnlyContextMixin(object):
    _add_non_stubs_in_filter = False

    def is_stub(self):
        return True

    def _get_stub_only_filters(self, **filter_kwargs):
        return [StubOnlyFilter(
            self.evaluator,
            context=self,
            **filter_kwargs
        )]

    def _get_base_filters(self, filters, search_global=False,
                          until_position=None, origin_scope=None):
        next(filters)  # Ignore the first filter and replace it with our own
        stub_only_filters = self._get_stub_only_filters(
            search_global=search_global,
            until_position=until_position,
            origin_scope=origin_scope,
        )
        for f in stub_only_filters:
            yield f

        for f in filters:
            yield f


class StubOnlyModuleContext(_StubOnlyContextMixin, ModuleContext):
    _add_non_stubs_in_filter = True

    def __init__(self, non_stub_context_set, *args, **kwargs):
        super(StubOnlyModuleContext, self).__init__(*args, **kwargs)
        self.non_stub_context_set = non_stub_context_set

    def _get_first_non_stub_filters(self):
        for context in self.non_stub_context_set:
            yield next(context.get_filters(search_global=False))

    def _get_stub_only_filters(self, search_global, **filter_kwargs):
        stub_filters = super(StubOnlyModuleContext, self)._get_stub_only_filters(
            search_global=search_global, **filter_kwargs
        )
        stub_filters += self.iter_star_filters(search_global=search_global)
        return stub_filters

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(StubOnlyModuleContext, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        for f in self._get_base_filters(filters, search_global, until_position, origin_scope):
            yield f

    def _iter_modules(self, path):
        dirs = os.listdir(path)
        for name in dirs:
            if os.path.isdir(os.path.join(path, name)):
                yield (None, name, True)
            if name.endswith('.pyi'):
                yield (None, name[:-4], True)
        return []


class StubOnlyClass(_StubOnlyContextMixin, ClassMixin, ContextWrapper):
    pass


class _CompiledStubContext(ContextWrapper):
    def __init__(self, stub_context, compiled_context):
        super(_CompiledStubContext, self).__init__(stub_context)
        self._compiled_context = compiled_context

    def is_stub(self):
        return True

    def py__doc__(self, include_call_signature=False):
        doc = self._compiled_context.py__doc__()
        if include_call_signature:
            call_sig = get_call_signature_for_any(self._wrapped_context.tree_node)
            if call_sig is not None:
                doc = call_sig + '\n\n' + doc
        return doc


class CompiledStubFunction(_CompiledStubContext):
    pass


class CompiledStubClass(_StubOnlyContextMixin, _CompiledStubContext, ClassMixin):
    def _get_first_non_stub_filters(self):
        yield next(self._compiled_context.get_filters(search_global=False))

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = self._wrapped_context.get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        for f in self._get_base_filters(filters, search_global, until_position, origin_scope):
            yield f


class TypingModuleWrapper(StubOnlyModuleContext):
    def get_filters(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f


def goto_with_stubs_if_possible(name):
    return [name]
    # XXX
    root = name.parent_context.get_root_context()
    stub = root.get_root_context().stub_context
    if stub is None:
        return [name]

    qualified_names = name.parent_context.get_qualified_names()
    if qualified_names is None:
        return [name]

    stub_contexts = ContextSet([stub])
    for n in qualified_names:
        stub_contexts = stub_contexts.py__getattribute__(n)
    names = stub_contexts.py__getattribute__(name.string_name, is_goto=True)
    return [
        n
        for n in names
        if n.start_pos == name.start_pos and n.parent_context == name.parent_context
    ] or [name]


def goto_non_stub(parent_context, tree_name):
    contexts = stub_to_actual_context_set(parent_context)
    return contexts.py__getattribute__(tree_name, is_goto=True)


def stub_to_actual_context_set(stub_context, ignore_compiled=False):
    qualified_names = stub_context.get_qualified_names()
    if qualified_names is None:
        return NO_CONTEXTS

    stub_module = stub_context.get_root_context()

    if not stub_module.is_stub():
        return ContextSet([stub_context])

    assert isinstance(stub_module, StubOnlyModuleContext), stub_module
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
        # Using the tree_name is better, if it's available, becuase no
        # information is lost. If the name given is defineda as `foo: int` we
        # would otherwise land on int, which is not what we want. We want foo
        # from the non-stub module.
        if name.tree_name is None:
            actual_contexts = ContextSet.from_sets(
                stub_to_actual_context_set(c) for c in name.infer()
            )
            actual_contexts = actual_contexts.filter(lambda c: not c.is_compiled())
            if actual_contexts:
                for s in actual_contexts:
                    yield s.name
            else:
                yield name
        else:
            parent_context = name.parent_context
            if not parent_context.is_stub():
                yield name
                continue

            contexts = stub_to_actual_context_set(parent_context)
            if prefer_stub_to_compiled:
                # We don't really care about
                contexts = contexts.filter(lambda c: not c.is_compiled())

            new_names = contexts.py__getattribute__(name.tree_name, is_goto=True)

            if new_names:
                for n in new_names:
                    yield n
            else:
                yield name


def _load_or_get_stub_module(evaluator, names):
    return evaluator.stub_module_cache.get(names)


def load_stubs(context):
    root_context = context.get_root_context()
    stub_module = _load_or_get_stub_module(
        context.evaluator,
        root_context.string_names
    )
    if stub_module is None:
        return NO_CONTEXTS

    qualified_names = context.get_qualified_names()
    if qualified_names is None:
        return NO_CONTEXTS

    stub_contexts = ContextSet([stub_module])
    for name in qualified_names:
        stub_contexts = stub_contexts.py__getattribute__(name)

    if isinstance(context, AnnotatedClass):
        return ContextSet([
            context.annotate_other_class(c) if c.is_class() else c
            for c in stub_contexts
        ])
    return stub_contexts


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


class CompiledStubName(NameWrapper):
    def __init__(self, parent_context, compiled_name, stub_name):
        super(CompiledStubName, self).__init__(stub_name)
        self.parent_context = parent_context
        self._compiled_name = compiled_name

    @memoize_method
    @iterator_to_context_set
    def infer(self):
        compiled_contexts = self._compiled_name.infer()
        stub_contexts = self._wrapped_name.infer()

        if not compiled_contexts:
            for c in stub_contexts:
                yield c

        for actual_context in compiled_contexts:
            for stub_context in stub_contexts:
                if isinstance(stub_context, _CompiledStubContext):
                    # It's already a stub context, e.g. bytes in Python 2
                    # behaves this way.
                    yield stub_context
                elif stub_context.is_class():
                    assert not isinstance(stub_context, CompiledStubClass), \
                        "%s and %s" % (self._wrapped_name, self._compiled_name)
                    yield CompiledStubClass.create_cached(
                        stub_context.evaluator, stub_context, actual_context)
                elif stub_context.is_function():
                    yield CompiledStubFunction.create_cached(
                        stub_context.evaluator, stub_context, actual_context)
                else:
                    yield stub_context
            if not stub_contexts:
                yield actual_context


class StubOnlyName(TreeNameDefinition):
    def infer(self):
        inferred = super(StubOnlyName, self).infer()
        if self.string_name == 'version_info' and self.get_root_context().py__name__() == 'sys':
            return [VersionInfo(c) for c in inferred]

        return [
            StubOnlyClass.create_cached(c.evaluator, c) if isinstance(c, ClassContext) else c
            for c in inferred
        ]


class StubOnlyFilter(ParserTreeFilter):
    name_class = StubOnlyName

    def __init__(self, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubOnlyFilter, self).__init__(*args, **kwargs)

    def _is_name_reachable(self, name):
        if not super(StubOnlyFilter, self)._is_name_reachable(name):
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
