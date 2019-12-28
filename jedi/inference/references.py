from jedi.inference import imports
from jedi.inference.filters import ParserTreeFilter


def _resolve_names(definition_names, avoid_names=()):
    for name in definition_names:
        if name in avoid_names:
            # Avoiding recursions here, because goto on a module name lands
            # on the same module.
            continue

        if not isinstance(name, imports.SubModuleName):
            # SubModuleNames are not actually existing names but created
            # names when importing something like `import foo.bar.baz`.
            yield name

        if name.api_type == 'module':
            for name in _resolve_names(name.goto(), definition_names):
                yield name


def _dictionarize(names):
    return dict(
        (n if n.tree_name is None else n.tree_name, n)
        for n in names
    )


def _find_defining_names(module_context, tree_name):
    found_names = _find_names(module_context, tree_name)

    found_names |= set(_find_global_variables(found_names, tree_name.value))
    for name in list(found_names):
        if name.api_type == 'param' or name.tree_name is None \
                or name.tree_name.parent.type == 'trailer':
            continue
        found_names |= set(_add_names_in_same_context(name.parent_context, name.string_name))
    return set(_resolve_names(found_names))


def _find_names(module_context, tree_name):
    name = module_context.create_name(tree_name)
    found_names = set(name.goto())
    found_names.add(name)

    return set(_resolve_names(found_names))


def _add_names_in_same_context(context, string_name):
    if context.tree_node is None:
        return

    until_position = None
    while True:
        filter_ = ParserTreeFilter(
            parent_context=context,
            until_position=until_position,
        )
        names = set(filter_.get(string_name))
        if not names:
            break
        for name in names:
            yield name
        ordered = sorted(names, key=lambda x: x.start_pos)
        until_position = ordered[0].start_pos


def _find_global_variables(names, search_name):
    for name in names:
        if name.tree_name is None:
            continue
        module_context = name.get_root_context()
        try:
            method = module_context.get_global_filter
        except AttributeError:
            continue
        else:
            for global_name in method().get(search_name):
                yield global_name
                c = module_context.create_context(global_name.tree_name)
                for name in _add_names_in_same_context(c, global_name.string_name):
                    yield name


def find_references(module_context, tree_name):
    search_name = tree_name.value
    found_names = _find_defining_names(module_context, tree_name)
    found_names_dct = _dictionarize(found_names)

    module_contexts = set(d.get_root_context() for d in found_names)
    module_contexts = set(m for m in module_contexts if not m.is_compiled())

    non_matching_reference_maps = {}
    inf = module_context.inference_state
    potential_modules = imports.get_module_contexts_containing_name(
        inf, module_contexts, search_name
    )
    for module_context in potential_modules:
        for name_leaf in module_context.tree_node.get_used_names().get(search_name, []):
            new = _dictionarize(_find_names(module_context, name_leaf))
            if any(tree_name in found_names_dct for tree_name in new):
                found_names_dct.update(new)
                for tree_name in new:
                    for dct in non_matching_reference_maps.get(tree_name, []):
                        # A reference that was previously searched for matches
                        # with a now found name. Merge.
                        found_names_dct.update(dct)
                    try:
                        del non_matching_reference_maps[tree_name]
                    except KeyError:
                        pass
            else:
                for name in new:
                    non_matching_reference_maps.setdefault(name, []).append(new)
    return found_names_dct.values()
