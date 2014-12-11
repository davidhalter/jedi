"""
Test of keywords and ``jedi.keywords``
"""
import jedi
from jedi import Script, common


def test_goto_assignments_keyword():
    """
    Bug: goto assignments on ``in`` used to raise AttributeError::

      'unicode' object has no attribute 'generate_call_path'
    """
    Script('in').goto_assignments()


def test_keyword():
    """ github jedi-vim issue #44 """
    defs = Script("print").goto_definitions()
    assert [d.doc for d in defs]

    assert Script("import").goto_assignments() == []

    completions = Script("import", 1, 1).completions()
    assert len(completions) > 10 and 'if' in [c.name for c in completions]
    assert Script("assert").goto_definitions() == []
