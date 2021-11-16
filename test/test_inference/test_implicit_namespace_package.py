from test.helpers import example_dir, get_example_dir
from typing import Any, Iterable

import pytest

from jedi import Project


def test_implicit_namespace_package(Script):
    sys_path = [get_example_dir('implicit_namespace_package', 'ns1'),
                get_example_dir('implicit_namespace_package', 'ns2')]
    project = Project('.', sys_path=sys_path)

    def script_with_path(*args, **kwargs):
        return Script(project=project, *args, **kwargs)

    # goto definition
    assert script_with_path('from pkg import ns1_file').infer()
    assert script_with_path('from pkg import ns2_file').infer()
    assert not script_with_path('from pkg import ns3_file').infer()

    # goto assignment
    tests = {
        'from pkg.ns2_file import foo': 'ns2_file!',
        'from pkg.ns1_file import foo': 'ns1_file!',
    }
    for source, solution in tests.items():
        ass = script_with_path(source).goto()
        assert len(ass) == 1
        assert ass[0].description == "foo = '%s'" % solution

    # completion
    completions = script_with_path('from pkg import ').complete()
    names = [c.name for c in completions]
    compare = ['ns1_file', 'ns2_file', 'subpkg']
    # must at least contain these items, other items are not important
    assert set(compare) == set(names)

    tests = {
        'from pkg import ns2_file as x': 'ns2_file!',
        'from pkg import ns1_file as x': 'ns1_file!'
    }
    for source, solution in tests.items():
        for c in script_with_path(source + '; x.').complete():
            if c.name == 'foo':
                completion = c
        solution = "foo = '%s'" % solution
        assert completion.description == solution


def test_implicit_nested_namespace_package(Script):
    code = 'from implicit_nested_namespaces.namespace.pkg.module import CONST'

    project = Project('.', sys_path=[example_dir])
    script = Script(code, project=project)

    result = script.infer(line=1, column=61)

    assert len(result) == 1

    implicit_pkg, = Script(code, project=project).infer(column=10)
    assert implicit_pkg.type == 'namespace'
    assert implicit_pkg.module_path is None


def test_implicit_namespace_package_import_autocomplete(Script):
    code = 'from implicit_name'

    project = Project('.', sys_path=[example_dir])
    script = Script(code, project=project)
    compl = script.complete()
    assert [c.name for c in compl] == ['implicit_namespace_package']


@pytest.mark.parametrize(
    'code,expected',
    [
        ('from pkg.', ['ns1_file', 'ns2_file', 'subpkg']),
        ('from pkg.subpkg.', ['ns3_file', 'ns4_file']),
    ]
)
def test_namespace_package_in_multiple_directories_autocompletion(
    code: str,
    expected: Iterable[str],
    Script: Any,
) -> None:
    sys_path = [get_example_dir('implicit_namespace_package', 'ns1'),
                get_example_dir('implicit_namespace_package', 'ns2')]

    project = Project('.', sys_path=sys_path)
    script = Script(code, project=project)
    compl = script.complete()
    assert set(c.name for c in compl) == set(expected)


@pytest.mark.parametrize(
    'code',
    [
        'from pkg import ns1_file',
        'from pkg import ns2_file',
        'from pkg.subpkg import ns3_file',
        'from pkg.subpkg import ns4_file',
    ]
)
def test_namespace_package_in_multiple_directories_goto_definition(
    code: str,
    Script: Any,
) -> None:
    sys_path = [get_example_dir('implicit_namespace_package', 'ns1'),
                get_example_dir('implicit_namespace_package', 'ns2')]
    project = Project('.', sys_path=sys_path)
    script = Script(code, project=project)
    result = script.infer()
    assert len(result) == 1


def test_namespace_name_autocompletion_full_name(Script):
    code = 'from pk'
    sys_path = [get_example_dir('implicit_namespace_package', 'ns1'),
                get_example_dir('implicit_namespace_package', 'ns2')]

    project = Project('.', sys_path=sys_path)
    script = Script(code, project=project)
    compl = script.complete()
    assert set(c.full_name for c in compl) == set(['pkg'])
