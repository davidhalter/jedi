"""
Tests ``from __future__ import absolute_import`` (only important for
Python 2.X)
"""
import jedi
from jedi.parser.python import parse
from .. import helpers


def test_explicit_absolute_imports():
    """
    Detect modules with ``from __future__ import absolute_import``.
    """
    module = parse("from __future__ import absolute_import")
    assert module.has_explicit_absolute_import


def test_no_explicit_absolute_imports():
    """
     Detect modules without ``from __future__ import absolute_import``.
    """
    assert not parse("1").has_explicit_absolute_import


def test_dont_break_imports_without_namespaces():
    """
    The code checking for ``from __future__ import absolute_import`` shouldn't
    assume that all imports have non-``None`` namespaces.
    """
    src = "from __future__ import absolute_import\nimport xyzzy"
    assert parse(src).has_explicit_absolute_import


@helpers.cwd_at("test/test_evaluate/absolute_import")
def test_can_complete_when_shadowing():
    script = jedi.Script(path="unittest.py")
    assert script.completions()
