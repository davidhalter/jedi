from os.path import join

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
