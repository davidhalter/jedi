import pytest

from jedi import settings
from jedi.inference.names import ValueName
from jedi.inference.compiled import CompiledValueName
from jedi.inference.gradual.typeshed import StubModuleValue


@pytest.fixture()
def auto_import_json(monkeypatch):
    monkeypatch.setattr(settings, 'auto_import_modules', ['json'])


def test_base_auto_import_modules(auto_import_json, Script):
    loads, = Script('import json; json.loads').infer()
    assert isinstance(loads._name, ValueName)
    value, = loads._name.infer()
    assert isinstance(value.parent_context._value, StubModuleValue)


def test_auto_import_modules_imports(auto_import_json, Script):
    main, = Script('from json import tool; tool.main').infer()
    assert isinstance(main._name, CompiledValueName)


def test_additional_dynamic_modules(monkeypatch, Script):
    # We could add further tests, but for now it's even more important that
    # this doesn't fail.
    monkeypatch.setattr(
        settings,
        'additional_dynamic_modules',
        ['/foo/bar/jedi_not_existing_file.py']
    )
    assert not Script('def some_func(f):\n f.').complete()


def test_cropped_file_size(monkeypatch, names, Script):
    code = 'class Foo(): pass\n'
    monkeypatch.setattr(
        settings,
        '_cropped_file_size',
        len(code)
    )

    foo, = names(code + code)
    assert foo.line == 1

    # It should just not crash if we are outside of the cropped range.
    script = Script(code + code + 'Foo')
    assert not script.infer()
    assert 'Foo' in [c.name for c in script.complete()]
