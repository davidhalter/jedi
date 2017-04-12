"""
Tests ``from __future__ import absolute_import`` (only important for
Python 2.X)
"""
import jedi
from .. import helpers


@helpers.cwd_at("test/test_evaluate/absolute_import")
def test_can_complete_when_shadowing():
    script = jedi.Script(path="unittest.py")
    assert script.completions()
