from jedi import settings
from jedi.evaluate.compiled import CompiledContextName


def test_base_auto_import_modules(monkeypatch, Script):
    monkeypatch.setattr(settings, 'auto_import_modules', ['json'])
    loads, = Script('import json; json.loads').goto_definitions()
    assert isinstance(loads._name, CompiledContextName)
