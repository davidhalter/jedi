import pytest

from jedi import settings
from jedi.evaluate.compiled import CompiledContextName


@pytest.fixture()
def auto_import_json(monkeypatch):
    monkeypatch.setattr(settings, 'auto_import_modules', ['json'])


def test_base_auto_import_modules(auto_import_json, Script):
    loads, = Script('import json; json.loads').goto_definitions()
    assert isinstance(loads._name, CompiledContextName)


def test_auto_import_modules_imports(auto_import_json, Script):
    main, = Script('from json import tool; tool.main').goto_definitions()
    assert isinstance(main._name, CompiledContextName)
