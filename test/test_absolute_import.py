"""
Tests ``from __future__ import absolute_import`` (only important for
Python 2.X)
"""
import jedi
from jedi.parsing import Parser
from . import helpers


def test_explicit_absolute_imports():
    """
    Detect modules with ``from __future__ import absolute_import``.
    """
    parser = Parser("from __future__ import absolute_import", "test.py")
    assert parser.module.has_explicit_absolute_import


def test_no_explicit_absolute_imports():
    """
     Detect modules without ``from __future__ import absolute_import``.
    """
    parser = Parser("1", "test.py")
    assert not parser.module.has_explicit_absolute_import


def test_dont_break_imports_without_namespaces():
    """
    The code checking for ``from __future__ import absolute_import`` shouldn't
    assume that all imports have non-``None`` namespaces.
    """
    src = "from __future__ import absolute_import\nimport xyzzy"
    parser = Parser(src, "test.py")
    assert parser.module.has_explicit_absolute_import


@helpers.cwd_at("test/absolute_import")
def test_can_complete_when_shadowing():
    filename = "unittest.py"
    with open(filename) as f:
        lines = f.readlines()
    src = "".join(lines)
    script = jedi.Script(src, len(lines), len(lines[1]), filename)
    assert script.completions()
