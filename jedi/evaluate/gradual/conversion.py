from jedi.evaluate.base_context import ContextSet, \
    NO_CONTEXTS
from jedi.evaluate.utils import to_list
from jedi.evaluate.gradual.stub_context import StubModuleContext


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
