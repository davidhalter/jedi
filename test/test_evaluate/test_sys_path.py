import os
from glob import glob
import sys
import shutil

import pytest
from jedi.evaluate import sys_path
from jedi import find_virtualenvs
from jedi.api.environment import Environment


def test_paths_from_assignment(Script):
    def paths(src):
        script = Script(src, path='/foo/bar.py')
        expr_stmt = script._get_module_node().children[0]
        return set(sys_path._paths_from_assignment(script._get_module(), expr_stmt))

    assert paths('sys.path[0:0] = ["a"]') == {'/foo/a'}
    assert paths('sys.path = ["b", 1, x + 3, y, "c"]') == {'/foo/b', '/foo/c'}
    assert paths('sys.path = a = ["a"]') == {'/foo/a'}

    # Fail for complicated examples.
    assert paths('sys.path, other = ["a"], 2') == set()


def test_venv_and_pths(tmpdir, environment):
    if environment.version_info.major < 3:
        pytest.skip("python -m venv does not exist in Python 2")

    pjoin = os.path.join

    dirname = pjoin(tmpdir.dirname, 'venv')

    # Ignore if it fails. It usually fails if it's not able to properly install
    # pip. However we don't need that for this test.
    executable_path = '/usr/bin/' + os.path.basename(environment._executable)
    if not os.path.exists(executable_path):
        # Need to not use the path in the virtualenv. Since tox creates
        # virtualenvs we cannot reuse them, because they have different site.py
        # files that work differently than the default ones.
        # Since nobody creates venv's from within virtualenvs (doesn't make
        # sense and people are hopefully starting to avoid virtualenv now -
        # because it's more complicated than venv), it's the correct approach
        # to just use the systems Python directly.
        # This doesn't work for windows and others, but I currently don't care.
        # Feel free to improve.
        pytest.skip()

    os.system(executable_path + ' -m venv ' + dirname)

    # We cannot find the virtualenv in some cases, because the virtualenv was
    # not created correctly.
    virtualenv = Environment(dirname, pjoin(dirname, 'bin', 'python'))

    CUR_DIR = os.path.dirname(__file__)
    site_pkg_path = glob(pjoin(virtualenv._base_path, 'lib', 'python*', 'site-packages'))[0]
    shutil.rmtree(site_pkg_path)
    shutil.copytree(pjoin(CUR_DIR, 'sample_venvs/pth_directory'), site_pkg_path)

    venv_paths = virtualenv.get_sys_path()

    ETALON = [
        # For now disable egg-links. I have no idea how they work... ~ dave
        #pjoin('/path', 'from', 'egg-link'),
        #pjoin(site_pkg_path, '.', 'relative', 'egg-link', 'path'),
        site_pkg_path,
        pjoin(site_pkg_path, 'dir-from-foo-pth'),
        '/foo/smth.py:module',
        # Not sure why it's added twice. It has to do with site.py which is not
        # something we can change. However this obviously also doesn't matter.
        '/foo/smth.py:from_func',
        '/foo/smth.py:from_func',
    ]

    # Ensure that pth and egg-link paths were added.
    assert venv_paths[-len(ETALON):] == ETALON

    # Ensure that none of venv dirs leaked to the interpreter.
    assert not set(sys.path).intersection(ETALON)
