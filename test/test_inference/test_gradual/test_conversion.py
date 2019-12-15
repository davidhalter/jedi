import os

from test.helpers import root_dir
from jedi.api.project import Project
from jedi.inference.gradual.conversion import convert_names


def test_sqlite3_conversion(Script):
    script1 = Script('import sqlite3; sqlite3.Connection')
    d, = script1.goto_definitions()

    assert not d.module_path
    assert d.full_name == 'sqlite3.Connection'
    assert convert_names([d._name], only_stubs=True)

    d, = script1.goto_definitions(only_stubs=True)
    assert d.is_stub()
    assert d.full_name == 'sqlite3.dbapi2.Connection'

    script2 = Script(path=d.module_path, line=d.line, column=d.column)
    d, = script2.goto_definitions()
    assert not d.is_stub()
    assert d.full_name == 'sqlite3.Connection'
    v, = d._name.infer()
    assert v.is_compiled()


def test_conversion_of_stub_only(Script):
    project = Project(os.path.join(root_dir, 'test', 'completion', 'stub_folder'))
    code = 'import stub_only; stub_only.in_stub_only'
    d1, = Script(code, _project=project).goto_assignments()
    assert d1.is_stub()

    script = Script(path=d1.module_path, line=d1.line, column=d1.column, _project=project)
    d2, = script.goto_assignments()
    assert d2.is_stub()
    assert d2.module_path == d1.module_path
    assert d2.line == d1.line
    assert d2.column == d1.column
    assert d2.name == 'in_stub_only'
