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
