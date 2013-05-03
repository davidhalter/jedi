import sys
if sys.hexversion < 0x02070000:
    import unittest2 as unittest
else:
    import unittest
import os
from os.path import abspath, dirname
import functools

import jedi


test_dir = dirname(abspath(__file__))
root_dir = dirname(test_dir)


sample_int = 1  # This is used in completion/imports.py


class TestBase(unittest.TestCase):
    def get_script(self, src, pos, path=None):
        if pos is None:
            lines = src.splitlines()
            pos = len(lines), len(lines[-1])
        return jedi.Script(src, pos[0], pos[1], path)

    def goto_definitions(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.goto_definitions()

    def completions(self, src, pos=None, path=None):
        script = self.get_script(src, pos, path)
        return script.completions()

    def goto_assignments(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.goto_assignments()

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
