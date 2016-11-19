from jedi._compatibility import unicode
from jedi.api import classes
from jedi.parser import tree
from jedi.evaluate import imports
from jedi.evaluate.filters import TreeNameDefinition


def usages(evaluator, definition_names, mods):
    """
    :param definitions: list of Name
    """
    def compare_array(definitions):
        """ `definitions` are being compared by module/start_pos, because
        sometimes the id's of the objects change (e.g. executions).
        """
        result = []
        for d in definitions:
            module = d.get_root_context()
            result.append((module, d.start_pos))
        return result

    search_name = list(definition_names)[0].string_name
    compare_definitions = compare_array(definition_names)
    mods = mods | set([d.get_root_context() for d in definition_names])
    definitions = []
    for m in imports.get_modules_containing_name(evaluator, mods, search_name):
        for name_node in m.module_node.used_names.get(search_name, []):
            context = evaluator.create_context(m, name_node)
            result = evaluator.goto(context, name_node)
            if [c for c in compare_array(result) if c in compare_definitions]:
                name = TreeNameDefinition(context, name_node)
                definitions.append(classes.Definition(evaluator, name))
                # Previous definitions might be imports, so include them
                # (because goto might return that import name).
                compare_definitions += compare_array([name])
    return definitions


def usages_add_import_modules(evaluator, definitions):
    """ Adds the modules of the imports """
    new = set()
    for d in definitions:
        print(d)
        imp_or_stmt = d.get_definition()
        if isinstance(imp_or_stmt, tree.Import):
            s = imports.ImportWrapper(context, d)
            new |= set(s.follow(is_goto=True))
    return set(definitions) | new
