import sys
if sys.hexversion < 0x02070000:
    import unittest2 as unittest
else:
    import unittest
import os
from os.path import abspath, dirname
import functools

test_dir = dirname(abspath(__file__))
root_dir = dirname(test_dir)

import pytest

import jedi
from jedi._compatibility import is_py25


sample_int = 1  # This is used in completion/imports.py


class TestBase(unittest.TestCase):
    def get_script(self, src, pos, path=None):
        if pos is None:
            lines = src.splitlines()
            pos = len(lines), len(lines[-1])
        return jedi.Script(src, pos[0], pos[1], path)

    def definition(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.definition()

    def complete(self, src, pos=None, path=None):
        script = self.get_script(src, pos, path)
        return script.complete()

    def goto(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.goto()

    def function_definition(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.function_definition()


def cwd_at(path):
    """
    Decorator to run function at `path`.

    :type path: str
    :arg  path: relative path from repository root (e.g., ``'jedi'``).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            try:
                oldcwd = os.getcwd()
                repo_root = os.path.dirname(test_dir)
                os.chdir(os.path.join(repo_root, path))
                return func(*args, **kwds)
            finally:
                os.chdir(oldcwd)
        return wrapper
    return decorator


_py25_fails = 0
py25_allowed_fails = 9


def skip_py25_fails(func):
    """
    Skip first `py25_allowed_fails` failures in Python 2.5.

    .. todo:: Remove this decorator by implementing "skip tag" for
       integration tests.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        global _py25_fails
        try:
            func(*args, **kwds)
        except AssertionError:
            _py25_fails += 1
            if _py25_fails > py25_allowed_fails:
                raise
            else:
                pytest.skip("%d-th failure (there can be %d failures)" %
                            (_py25_fails, py25_allowed_fails))
    return wrapper

if not is_py25:
    skip_py25_fails = lambda f: f
