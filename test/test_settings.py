import pytest

from jedi import settings
from jedi.evaluate.names import ContextName
from jedi.evaluate.compiled import CompiledContextName
from jedi.evaluate.gradual.typeshed import StubModuleContext


@pytest.fixture()
def auto_import_json(monkeypatch):
    monkeypatch.setattr(settings, 'auto_import_modules', ['json'])


def test_base_auto_import_modules(auto_import_json, Script):
    loads, = Script('import json; json.loads').goto_definitions()
    assert isinstance(loads._name, ContextName)
    context, = loads._name.infer()
    assert isinstance(context.parent_context, StubModuleContext)


def test_auto_import_modules_imports(auto_import_json, Script):
    main, = Script('from json import tool; tool.main').goto_definitions()
    assert isinstance(main._name, CompiledContextName)


def test_additional_dynamic_modules(monkeypatch, Script):
    # We could add further tests, but for now it's even more important that
    # this doesn't fail.
    monkeypatch.setattr(
        settings,
        'additional_dynamic_modules',
        ['/foo/bar/jedi_not_existing_file.py']
    )
    assert not Script('def some_func(f):\n f.').completions()
