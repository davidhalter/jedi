import time
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
sys.path.insert(0, root_dir)

import jedi
from jedi import debug

test_sum = 0
t_start = time.time()
# Sorry I didn't use argparse here. It's because argparse is not in the
# stdlib in 2.5.
args = sys.argv[1:]

print_debug = False
try:
    i = args.index('--debug')
    args = args[:i] + args[i + 1:]
except ValueError:
    pass
else:
    print_debug = True
    jedi.set_debug_function(debug.print_to_stdout)

sys.argv = sys.argv[:1] + args

summary = []
tests_fail = 0


def get_test_list():
# get test list, that should be executed
    test_files = {}
    last = None
    for arg in sys.argv[1:]:
        if arg.isdigit():
            if last is None:
                continue
            test_files[last].append(int(arg))
        else:
            test_files[arg] = []
            last = arg
    return test_files


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


def print_summary():
    print('\nSummary: (%s fails of %s tests) in %.3fs' % \
                                (tests_fail, test_sum, time.time() - t_start))
    for s in summary:
        print(s)


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
