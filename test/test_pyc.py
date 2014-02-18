"""
Test completions from *.pyc files:

 - generate a dummy python module
 - compile the dummy module to generate a *.pyc
 - delete the pure python dummy module
 - try jedi on the generated *.pyc
"""
import compileall
import os
import shutil
import sys

import jedi


SRC = """class Foo:
    pass

class Bar:
    pass
"""


def generate_pyc():
    with open("dummy.py", 'w') as f:
        f.write(SRC)
    compileall.compile_file("dummy.py")
    os.remove("dummy.py")

    if sys.version_info[0] == 3:
        # Python3 specific:
        # To import pyc modules, we must move them out of the __pycache__
        # directory and rename them to remove ".cpython-%s%d"
        # see: http://stackoverflow.com/questions/11648440/python-does-not-detect-pyc-files
        for f in os.listdir("__pycache__"):
            dst = f.replace('.cpython-%s%s' % sys.version_info[:2], "")
            shutil.copy(os.path.join("__pycache__", f), dst)


def test_pyc():
    """
    The list of completion must be greater than 2.
    """
    generate_pyc()
    s = jedi.Script("import dummy; dummy.")
    assert len(s.completions()) >= 2


if __name__ == "__main__":
    test_pyc()
