from jedi.parsing import Parser
from jedi._compatibility import is_py3k; is_py3k # shut up pyflakes
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

def test_imports_are_absolute_in_modules_with_future_import():
    """
    In any module with the ``absolute_import`` ``__future__`` import, all
    imports are absolute.
    """
    parser = Parser("from __future__ import absolute_import", "test.py")
    assert parser.scope.absolute_imports
