import os

from jedi._compatibility import u
from jedi.evaluate.sys_path import (_get_parent_dir_with_file,
                                    _get_buildout_scripts,
                                    _check_module)
from jedi.parser import Parser

from ..helpers import cwd_at


@cwd_at('test/test_evaluate/buildout_project/src/proj_name')
def test_parent_dir_with_file():
    parent = _get_parent_dir_with_file(
        os.path.abspath(os.curdir), 'buildout.cfg')
    assert parent is not None
    assert parent.endswith(os.path.join('test', 'test_evaluate', 'buildout_project'))


@cwd_at('test/test_evaluate/buildout_project/src/proj_name')
def test_buildout_detection():
    scripts = _get_buildout_scripts(os.path.abspath('./module_name.py'))
    assert len(scripts) == 1
    curdir = os.path.abspath(os.curdir)
    appdir_path = os.path.normpath(os.path.join(curdir, '../../bin/app'))
    assert scripts[0] == appdir_path


def test_append_on_non_sys_path():
    SRC = u("""
class Dummy(object):
    path = []

d = Dummy()
d.path.append('foo')""")
    p = Parser(SRC)
    paths = _check_module(p.module)
    assert len(paths) > 0
    assert 'foo' not in paths


def test_path_from_invalid_sys_path_assignment():
    SRC = u("""
import sys
sys.path = 'invalid'""")
    p = Parser(SRC)
    paths = _check_module(p.module)
    assert len(paths) > 0
    assert 'invalid' not in paths


def test_path_from_sys_path_assignment():
    SRC = u("""
#!/usr/bin/python

import sys
sys.path[0:0] = [
  '/usr/lib/python3.4/site-packages',
  '/home/test/.buildout/eggs/important_package.egg'
  ]

path[0:0] = [1]

import important_package

if __name__ == '__main__':
    sys.exit(important_package.main())""")
    p = Parser(SRC)
    paths = _check_module(p.module)
    assert 1 not in paths
    assert '/home/test/.buildout/eggs/important_package.egg' in paths
