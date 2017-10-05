import os
from glob import glob
import sys

import pytest

from jedi.evaluate import sys_path
from jedi import Script


def test_paths_from_assignment():
    def paths(src):
        script = Script(src, path='/foo/bar.py')
        expr_stmt = script._get_module_node().children[0]
        return set(sys_path._paths_from_assignment(script._get_module(), expr_stmt))

    assert paths('sys.path[0:0] = ["a"]') == set(['/foo/a'])
    assert paths('sys.path = ["b", 1, x + 3, y, "c"]') == set(['/foo/b', '/foo/c'])
    assert paths('sys.path = a = ["a"]') == set(['/foo/a'])

    # Fail for complicated examples.
    assert paths('sys.path, other = ["a"], 2') == set()


# Currently venv site-packages resolution only seeks pythonX.Y/site-packages
# that belong to the same version as the interpreter to avoid issues with
# cross-version imports.  "venvs/" dir contains "venv27" and "venv34" that
# mimic venvs created for py2.7 and py3.4 respectively.  If test runner is
# invoked with one of those versions, the test below will be run for the
# matching directory.
CUR_DIR = os.path.dirname(__file__)
VENVS = list(glob(
    os.path.join(CUR_DIR, 'sample_venvs/venv%d%d' % sys.version_info[:2])))


@pytest.mark.parametrize('venv', VENVS)
def test_get_venv_path(venv):
    pjoin = os.path.join
    venv_path = sys_path.get_venv_path(venv)

    site_pkgs = (glob(pjoin(venv, 'lib', 'python*', 'site-packages')) +
                 glob(pjoin(venv, 'lib', 'site-packages')))[0]
    ETALON = [
        pjoin('/path', 'from', 'egg-link'),
        pjoin(site_pkgs, '.', 'relative', 'egg-link', 'path'),
        site_pkgs,
        pjoin(site_pkgs, 'dir-from-foo-pth'),
    ]

    # Ensure that pth and egg-link paths were added.
    assert venv_path[:len(ETALON)] == ETALON

    # Ensure that none of venv dirs leaked to the interpreter.
    assert not set(sys.path).intersection(ETALON)

    # Ensure that "import ..." lines were ignored.
    assert pjoin('/path', 'from', 'smth.py') not in venv_path
    assert pjoin('/path', 'from', 'smth.py:extend_path') not in venv_path
