"""
Test completions from *.pyc files:

 - generate a dummy python module
 - compile the dummy module to generate a *.pyc
 - delete the pure python dummy module
 - try jedi on the generated *.pyc
"""
import os
import shutil
import sys

import jedi
from ..helpers import cwd_at


SRC = """class Foo:
    pass

class Bar:
    pass
"""


def generate_pyc():
    os.mkdir("dummy_package")
    with open("dummy_package/__init__.py", 'w'):
        pass
    with open("dummy_package/dummy.py", 'w') as f:
        f.write(SRC)
    import compileall
    compileall.compile_file("dummy_package/dummy.py")
    os.remove("dummy_package/dummy.py")

    if sys.version_info[0] == 3:
        # Python3 specific:
        # To import pyc modules, we must move them out of the __pycache__
        # directory and rename them to remove ".cpython-%s%d"
        # see: http://stackoverflow.com/questions/11648440/python-does-not-detect-pyc-files
        for f in os.listdir("dummy_package/__pycache__"):
            dst = f.replace('.cpython-%s%s' % sys.version_info[:2], "")
            dst = os.path.join("dummy_package", dst)
            shutil.copy(os.path.join("dummy_package/__pycache__", f), dst)


@cwd_at('test/test_evaluate')
def test_pyc(Script):
    """
    The list of completion must be greater than 2.
    """
    try:
        generate_pyc()
        s = jedi.Script("from dummy_package import dummy; dummy.", path='blub.py')
        assert len(s.completions()) >= 2
    finally:
        shutil.rmtree("dummy_package")
