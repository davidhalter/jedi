"""
A helper module for testing, improves compatibility for testing (as
``jedi._compatibility``) as well as introducing helper functions.
"""

import sys
if sys.hexversion < 0x02070000:
    import unittest2 as unittest
else:
    import unittest
TestCase = unittest.TestCase

import os
from os.path import abspath, dirname
import functools

test_dir = dirname(abspath(__file__))
root_dir = dirname(test_dir)

sample_int = 1  # This is used in completion/imports.py

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
