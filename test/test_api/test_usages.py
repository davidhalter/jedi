import jedi
import os.path

def test_import_usage():
    s = jedi.Script("from .. import foo", line=1, column=18, path="foo.py")
    assert [usage.line for usage in s.usages()] == [1]


def usages_with_additional_modules(script, additional_modules):
    """
    Stripped down version of `jedi.api.Script.usages` that can take an
    explicit set of additional modules. For use with `test_cross_module_usages`.
    """

    definition_names = jedi.api.usages.resolve_potential_imports(script._evaluator,
                                                        script._goto())
    modules = set([d.get_root_context() for d in definition_names])
    modules.add(script._get_module())
    for additional_module in additional_modules:
        modules.add(additional_module._name.get_root_context())
    return jedi.api.usages.usages(script._evaluator, definition_names, modules)


def test_cross_module_usages():
    """
    This tests finding of usages between different modules. In
    `jedi.api.usages.compare_contexts`, this exercises the case where
    `c1 != c2`. This tests whether `jedi` can find the usage of
    `import_tree_for_usages.b.bar` in `import_tree_for_usages.a`
    """

    def usages_script():
        source = 'import import_tree_for_usages.b; import_tree_for_usages.b.bar'
        return jedi.api.Script(source=source, line=1, column=len(source),
                               sys_path=[os.path.dirname(os.path.abspath(__file__))])

    def module_script():
        source = 'import import_tree_for_usages.a; import_tree_for_usages.a'
        return jedi.api.Script(source=source, line=1, column=len(source),
                               sys_path=[os.path.dirname(os.path.abspath(__file__))])

    module = module_script().goto_definitions()[0]
    module_definition = module._name.get_root_context()
    usages_list = usages_with_additional_modules(usages_script(), set([module]))

    assert any([elt for elt in usages_list if elt.module_name == 'a']), (
        "Did not find cross-module usage of :func:`b.bar` in :mod:`a`. Usages list was: {}"
        .format(usages_list))
