import os
from glob import glob
import sys
import shutil
import subprocess

import pytest
from jedi.evaluate import sys_path
from jedi import find_virtualenvs
from jedi.api.environment import Environment


def test_paths_from_assignment(Script):
    def paths(src):
        script = Script(src, path='/foo/bar.py')
        expr_stmt = script._module_node.children[0]
        return set(sys_path._paths_from_assignment(script._get_module(), expr_stmt))

    # Normalize paths for Windows.
    path_a = os.path.abspath('/foo/a')
    path_b = os.path.abspath('/foo/b')
    path_c = os.path.abspath('/foo/c')

    assert paths('sys.path[0:0] = ["a"]') == {path_a}
    assert paths('sys.path = ["b", 1, x + 3, y, "c"]') == {path_b, path_c}
    assert paths('sys.path = a = ["a"]') == {path_a}

    # Fail for complicated examples.
    assert paths('sys.path, other = ["a"], 2') == set()


def test_venv_and_pths(tmpdir, environment):
    if environment.version_info.major < 3:
        pytest.skip("python -m venv does not exist in Python 2")

    pjoin = os.path.join

    dirname = pjoin(tmpdir.dirname, 'venv')

    # We cannot use the Python from tox because tox creates virtualenvs and they
    # have different site.py files that work differently than the default ones.
    # Instead, we find the real Python executable by printing the value of
    # sys.base_prefix or sys.real_prefix if we are in a virtualenv.
    output = subprocess.check_output([
      environment._executable, "-c",
      "import sys; "
      "print(sys.real_prefix if hasattr(sys, 'real_prefix') else "
            "sys.base_prefix)"
    ])
    prefix = output.rstrip().decode('utf8')
    if os.name == 'nt':
        executable_path = os.path.join(prefix, 'python')
    else:
        executable_name = os.path.basename(environment._executable)
        executable_path = os.path.join(prefix, 'bin', executable_name)

    subprocess.call([executable_path, '-m', 'venv', dirname])

    bin_name = 'Scripts' if os.name == 'nt' else 'bin'
    virtualenv = Environment(dirname, pjoin(dirname, bin_name, 'python'))

    CUR_DIR = os.path.dirname(__file__)
    site_pkg_path = pjoin(virtualenv._base_path, 'lib')
    if os.name == 'nt':
        site_pkg_path = pjoin(site_pkg_path, 'site-packages')
    else:
        site_pkg_path = glob(pjoin(site_pkg_path, 'python*', 'site-packages'))[0]
    shutil.rmtree(site_pkg_path)
    shutil.copytree(pjoin(CUR_DIR, 'sample_venvs', 'pth_directory'), site_pkg_path)

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
