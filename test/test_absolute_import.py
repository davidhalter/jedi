import jedi
from jedi.parsing import Parser
from . import base


@base.py3_only
def test_py3k_imports_are_always_absolute():
    """
    By default, imports in Python 3 are absolute.
    """
    parser = Parser("1", "test.py")
    assert parser.scope.absolute_imports


@base.py2_only
def test_py2_imports_are_not_always_absolute():
    """
    By default, imports in Python 2 are not absolute.
    """
    parser = Parser("1", "test.py")
    assert not parser.scope.absolute_imports


def test_dont_break_imports_without_namespaces():
    """
    The code checking for ``from __future__ import absolute_import`` shouldn't
    assume that all imports have non-``None`` namespaces.
    """
    src = "from __future__ import absolute_import\nimport xyzzy"
    parser = Parser(src, "test.py")
    assert parser.scope.absolute_imports


def test_imports_are_absolute_in_modules_with_future_import():
    """
    In any module with the ``absolute_import`` ``__future__`` import, all
    imports are absolute.
    """
    parser = Parser("from __future__ import absolute_import", "test.py")
    assert parser.scope.absolute_imports


@base.cwd_at("test/absolute_import")
def test_can_complete_when_shadowing():
    filename = "unittest.py"
    with open(filename) as f:
        lines = f.readlines()
    src = "".join(lines)
    script = jedi.Script(src, len(lines), len(lines[1]), filename)
    assert script.completions()
