import jedi
from os.path import dirname, join


def test_namespace_package():
    sys_path = [join(dirname(__file__), d)
                for d in ['namespace_package/ns1', 'namespace_package/ns2']]

    def script_with_path(*args, **kwargs):
        return jedi.Script(sys_path=sys_path, *args, **kwargs)

    # goto definition
    assert script_with_path('from pkg import ns1_file').goto_definitions()
    assert script_with_path('from pkg import ns2_file').goto_definitions()
    assert not script_with_path('from pkg import ns3_file').goto_definitions()

    # goto assignment
    tests = {
        'from pkg.ns2_folder.nested import foo': 'nested!',
        'from pkg.ns2_folder import foo': 'ns2_folder!',
        'from pkg.ns2_file import foo': 'ns2_file!',
        'from pkg.ns1_folder import foo': 'ns1_folder!',
        'from pkg.ns1_file import foo': 'ns1_file!',
        'from pkg import foo': 'ns1!',
    }
    for source, solution in tests.items():
        ass = script_with_path(source).goto_assignments()
        assert len(ass) == 1
        assert ass[0].description == "foo = '%s'" % solution

    # completion
    completions = script_with_path('from pkg import ').completions()
    names = [str(c.name) for c in completions]  # str because of unicode
    compare = ['foo', 'ns1_file', 'ns1_folder', 'ns2_folder', 'ns2_file',
               'pkg_resources', 'pkgutil', '__name__', '__path__',
               '__package__', '__file__', '__doc__']
    # must at least contain these items, other items are not important
    assert set(compare) == set(names)

    tests = {
        'from pkg import ns2_folder as x': 'ns2_folder!',
        'from pkg import ns2_file as x': 'ns2_file!',
        'from pkg.ns2_folder import nested as x': 'nested!',
        'from pkg import ns1_folder as x': 'ns1_folder!',
        'from pkg import ns1_file as x': 'ns1_file!',
        'import pkg as x': 'ns1!',
    }
    for source, solution in tests.items():
        for c in script_with_path(source + '; x.').completions():
            if c.name == 'foo':
                completion = c
        solution = "foo = '%s'" % solution
        assert completion.description == solution


def test_nested_namespace_package():
    code = 'from nested_namespaces.namespace.pkg import CONST'

    sys_path = [dirname(__file__)]

    script = jedi.Script(sys_path=sys_path, source=code, line=1, column=45)

    result = script.goto_definitions()

    assert len(result) == 1
