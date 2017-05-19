from jedi.api import classes
from parso.python import tree
from jedi.evaluate import imports
from jedi.evaluate.filters import TreeNameDefinition
from jedi.evaluate.representation import ModuleContext


def compare_contexts(c1, c2):
    return c1 == c2 or (c1[1] == c2[1] and c1[0].tree_node == c2[0].tree_node)


def usages(evaluator, definition_names, mods):
    """
    :param definitions: list of Name
    """
    def resolve_names(definition_names):
        for name in definition_names:
            if name.api_type == 'module':
                found = False
                for context in name.infer():
                    if isinstance(context, ModuleContext):
                        found = True
                        yield context.name
                if not found:
                    yield name
            else:
                yield name

    def compare_array(definition_names):
        """ `definitions` are being compared by module/start_pos, because
        sometimes the id's of the objects change (e.g. executions).
        """
        return [
            (name.get_root_context(), name.start_pos)
            for name in resolve_names(definition_names)
        ]

    search_name = list(definition_names)[0].string_name
    compare_definitions = compare_array(definition_names)
    mods = mods | set([d.get_root_context() for d in definition_names])
    definition_names = set(resolve_names(definition_names))
    for m in imports.get_modules_containing_name(evaluator, mods, search_name):
        if isinstance(m, ModuleContext):
            for name_node in m.tree_node.get_used_names().get(search_name, []):
                context = evaluator.create_context(m, name_node)
                result = evaluator.goto(context, name_node)
                if any(compare_contexts(c1, c2)
                       for c1 in compare_array(result)
                       for c2 in compare_definitions):
                    name = TreeNameDefinition(context, name_node)
                    definition_names.add(name)
                    # Previous definitions might be imports, so include them
                    # (because goto might return that import name).
                    compare_definitions += compare_array([name])
        else:
            # compiled objects
            definition_names.add(m.name)

    return [classes.Definition(evaluator, n) for n in definition_names]


def resolve_potential_imports(evaluator, definitions):
    """ Adds the modules of the imports """
    new = set()
    for d in definitions:
        if isinstance(d, TreeNameDefinition):
            imp_or_stmt = d.tree_name.get_definition()
            if isinstance(imp_or_stmt, tree.Import):
                new |= resolve_potential_imports(
                    evaluator,
                    set(imports.infer_import(
                        d.parent_context, d.tree_name, is_goto=True
                    ))
                )
    return set(definitions) | new
