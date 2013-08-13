import jedi
import sys
from os.path import dirname, join

def test_namespace_package():
    sys.path.insert(0, join(dirname(__file__), 'namespace_package/ns1'))
    sys.path.insert(1, join(dirname(__file__), 'namespace_package/ns2'))
    try:
        # goto definition
        assert jedi.Script('from pkg import ns1_file').goto_definitions()
        assert jedi.Script('from pkg import ns2_file').goto_definitions()
        assert not jedi.Script('from pkg import ns3_file').goto_definitions()

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
            ass = jedi.Script(source).goto_assignments()
            assert len(ass) == 1
            assert ass[0].description == "foo = '%s'" % solution

        # completion
        completions = jedi.Script('from pkg import ').completions()
        names = [str(c.name) for c in completions]  # str because of unicode
        compare = ['foo', 'ns1_file', 'ns1_folder', 'ns2_folder', 'ns2_file']
        # must at least contain these items, other items are not important
        assert not (set(compare) - set(names))

        tests = {
            'from pkg import ns2_folder as x': 'ns2_folder!',
            'from pkg import ns2_file as x': 'ns2_file!',
            'from pkg.ns2_folder import nested as x': 'nested!',
            'from pkg import ns1_folder as x': 'ns1_folder!',
            'from pkg import ns1_file as x': 'ns1_file!',
            'import pkg as x': 'ns1!',
        }
        for source, solution in tests.items():
            for c in jedi.Script(source + '; x.').completions():
                if c.name == 'foo':
                    completion = c
            solution = "statement: foo = '%s'" % solution
            assert completion.description == solution


    finally:
        sys.path.pop(0)
        sys.path.pop(0)
