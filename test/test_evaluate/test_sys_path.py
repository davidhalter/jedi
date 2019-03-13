import os
from glob import glob
import sys
import shutil

import pytest

from jedi.evaluate import sys_path
from jedi.api.environment import create_environment


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


def test_venv_and_pths(venv_path):
    pjoin = os.path.join

    CUR_DIR = os.path.dirname(__file__)
    site_pkg_path = pjoin(venv_path, 'lib')
    if os.name == 'nt':
        site_pkg_path = pjoin(site_pkg_path, 'site-packages')
    else:
        site_pkg_path = glob(pjoin(site_pkg_path, 'python*', 'site-packages'))[0]
    shutil.rmtree(site_pkg_path)
    shutil.copytree(pjoin(CUR_DIR, 'sample_venvs', 'pth_directory'), site_pkg_path)

    virtualenv = create_environment(venv_path)
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


_s = ['/a', '/b', '/c/d/']


@pytest.mark.parametrize(
    'sys_path_, module_path, result', [
        (_s, '/a/b', ['b']),
        (_s, '/a/b/c', ['b', 'c']),
        (_s, '/a/b.py', ['b']),
        (_s, '/a/b/c.py', ['b', 'c']),
        (_s, '/x/b.py', None),
        (_s, '/c/d/x.py', ['x']),
        (_s, '/c/d/x.py', ['x']),
        (_s, '/c/d/x/y.py', ['x', 'y']),
        # If dots are in there they also resolve. These are obviously illegal
        # in Python, but Jedi can handle them. Give the user a bit more freedom
        # that he will have to correct eventually.
        (_s, '/a/b.c.py', ['b.c']),
        (_s, '/a/b.d/foo.bar.py', ['b.d', 'foo.bar']),

        (_s, '/a/.py', None),
        (_s, '/a/c/.py', None),
    ])
def test_calculate_dotted_from_path(sys_path_, module_path, result):
    # tranform_path_to_dotted expects normalized absolute paths.
    sys_path_ = [os.path.abspath(path) for path in sys_path_]
    module_path = os.path.abspath(module_path)
    assert sys_path.transform_path_to_dotted(sys_path_, module_path) == result
