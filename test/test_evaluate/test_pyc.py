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

import pytest

import jedi
from jedi.api.environment import SameEnvironment


SRC = """class Foo:
    pass

class Bar:
    pass
"""


@pytest.fixture
def pyc_project_path(tmpdir):
    path = tmpdir.strpath
    dummy_package_path = os.path.join(path, "dummy_package")
    os.mkdir(dummy_package_path)
    with open(os.path.join(dummy_package_path, "__init__.py"), 'w'):
        pass

    dummy_path = os.path.join(dummy_package_path, 'dummy.py')
    with open(dummy_path, 'w') as f:
        f.write(SRC)
    import compileall
    compileall.compile_file(dummy_path)
    os.remove(dummy_path)

    if sys.version_info.major == 3:
        # Python3 specific:
        # To import pyc modules, we must move them out of the __pycache__
        # directory and rename them to remove ".cpython-%s%d"
        # see: http://stackoverflow.com/questions/11648440/python-does-not-detect-pyc-files
        pycache = os.path.join(dummy_package_path, "__pycache__")
        for f in os.listdir(pycache):
            dst = f.replace('.cpython-%s%s' % sys.version_info[:2], "")
            dst = os.path.join(dummy_package_path, dst)
            shutil.copy(os.path.join(pycache, f), dst)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_pyc(pyc_project_path):
    """
    The list of completion must be greater than 2.
    """
    path = os.path.join(pyc_project_path, 'blub.py')
    s = jedi.Script(
        "from dummy_package import dummy; dummy.",
        path=path,
        environment=SameEnvironment())
    assert len(s.completions()) >= 2
