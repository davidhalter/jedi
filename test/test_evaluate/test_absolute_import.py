"""
Tests ``from __future__ import absolute_import`` (only important for
Python 2.X)
"""
import jedi
from jedi._compatibility import u
from jedi.parser import Parser
from .. import helpers


def test_explicit_absolute_imports():
    """
    Detect modules with ``from __future__ import absolute_import``.
    """
    parser = Parser(u("from __future__ import absolute_import"), "test.py")
    assert parser.module.has_explicit_absolute_import


def test_no_explicit_absolute_imports():
    """
     Detect modules without ``from __future__ import absolute_import``.
    """
    parser = Parser(u("1"), "test.py")
    assert not parser.module.has_explicit_absolute_import


def test_dont_break_imports_without_namespaces():
    """
    The code checking for ``from __future__ import absolute_import`` shouldn't
    assume that all imports have non-``None`` namespaces.
    """
    src = u("from __future__ import absolute_import\nimport xyzzy")
    parser = Parser(src, "test.py")
    assert parser.module.has_explicit_absolute_import


@helpers.cwd_at("test/test_evaluate/absolute_import")
def test_can_complete_when_shadowing():
    script = jedi.Script(path="unittest.py")
    assert script.completions()
