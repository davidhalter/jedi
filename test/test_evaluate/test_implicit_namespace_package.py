from os.path import dirname, join

import jedi
import pytest


@pytest.mark.skipif('sys.version_info[:2] < (3,4)')
def test_implicit_namespace_package():
    sys_path = [join(dirname(__file__), d)
                for d in ['implicit_namespace_package/ns1', 'implicit_namespace_package/ns2']]

    def script_with_path(*args, **kwargs):
        return jedi.Script(sys_path=sys_path, *args, **kwargs)

    # goto definition
    assert script_with_path('from pkg import ns1_file').goto_definitions()
    assert script_with_path('from pkg import ns2_file').goto_definitions()
    assert not script_with_path('from pkg import ns3_file').goto_definitions()

    # goto assignment
    tests = {
        'from pkg.ns2_file import foo': 'ns2_file!',
        'from pkg.ns1_file import foo': 'ns1_file!',
    }
    for source, solution in tests.items():
        ass = script_with_path(source).goto_assignments()
        assert len(ass) == 1
        assert ass[0].description == "foo = '%s'" % solution

    # completion
    completions = script_with_path('from pkg import ').completions()
    names = [c.name for c in completions]
    compare = ['ns1_file', 'ns2_file']
    # must at least contain these items, other items are not important
    assert set(compare) == set(names)

    tests = {
        'from pkg import ns2_file as x': 'ns2_file!',
        'from pkg import ns1_file as x': 'ns1_file!'
    }
    for source, solution in tests.items():
        for c in script_with_path(source + '; x.').completions():
            if c.name == 'foo':
                completion = c
        solution = "foo = '%s'" % solution
        assert completion.description == solution

@pytest.mark.skipif('sys.version_info[:2] < (3,4)')
def test_implicit_nested_namespace_package():
    CODE = 'from implicit_nested_namespaces.namespace.pkg.module import CONST'

    sys_path = [dirname(__file__)]

    script = jedi.Script(sys_path=sys_path, source=CODE, line=1, column=61)

    result = script.goto_definitions()

    assert len(result) == 1
