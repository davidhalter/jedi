import os

from jedi.evaluate.imports import JediImportError
from jedi.evaluate.gradual.typeshed import TYPESHED_PATH, create_stub_module


def load_proper_stub_module(evaluator, path, import_names, module_node):
    """
    This function is given a random .pyi file and should return the proper
    module.
    """
    assert path.endswith('.pyi')
    if path.startswith(TYPESHED_PATH):
        # /foo/stdlib/3/os/__init__.pyi -> stdlib/3/os/__init__
        rest = path[len(TYPESHED_PATH) + 1: -4]
        split_paths = tuple(rest.split(os.path.sep))
        # Remove the stdlib/3 or third_party/3.5 part
        import_names = split_paths[2:]
        if import_names[-1] == '__init__':
            import_names = import_names[:-1]

    if import_names is not None:
        try:
            actual_context_set = evaluator.import_module(import_names, load_stub=False)
        except JediImportError as e:
            return None

        context_set = create_stub_module(
            evaluator, actual_context_set, module_node, path, import_names
        )
        for m in context_set:
            # Try to load the modules in a way where they are loaded
            # correctly as stubs and not as actual modules (which is what
            # will happen if this condition isn't True).
            if m.stub_context.py__file__() == path:
                evaluator.module_cache.add(import_names, context_set)
                return m.stub_context
    return None
