"""
Tests of various import related things that could not be tested with "Black Box
Tests".
"""

import os
import sys

import pytest

import jedi
from jedi._compatibility import find_module_py33, find_module
from ..helpers import cwd_at

from jedi import Script
from jedi._compatibility import is_py26


@pytest.mark.skipif('sys.version_info < (3,3)')
def test_find_module_py33():
    """Needs to work like the old find_module."""
    assert find_module_py33('_io') == (None, '_io', False)


def test_find_module_package():
    file, path, is_package = find_module('json')
    assert file is None
    assert path.endswith('json')
    assert is_package is True


def test_find_module_not_package():
    file, path, is_package = find_module('io')
    assert file is not None
    assert path.endswith('io.py')
    assert is_package is False


def test_find_module_package_zipped():
    if 'zipped_imports/pkg.zip' not in sys.path:
      sys.path.append(os.path.join(os.path.dirname(__file__),
                      'zipped_imports/pkg.zip'))
    file, path, is_package = find_module('pkg')
    assert file is not None
    assert path.endswith('pkg.zip')
    assert is_package is True
    assert len(jedi.Script('import pkg; pkg.mod', 1, 19).completions()) == 1


@pytest.mark.skipif('sys.version_info < (2,7)')
def test_find_module_not_package_zipped():
    if 'zipped_imports/not_pkg.zip' not in sys.path:
      sys.path.append(os.path.join(os.path.dirname(__file__),
                      'zipped_imports/not_pkg.zip'))
    file, path, is_package = find_module('not_pkg')
    assert file is not None
    assert path.endswith('not_pkg.zip')
    assert is_package is False
    assert len(
      jedi.Script('import not_pkg; not_pkg.val', 1, 27).completions()) == 1


@cwd_at('test/test_evaluate/not_in_sys_path/pkg')
def test_import_not_in_sys_path():
    """
    non-direct imports (not in sys.path)
    """
    a = jedi.Script(path='module.py', line=5).goto_definitions()
    assert a[0].name == 'int'

    a = jedi.Script(path='module.py', line=6).goto_definitions()
    assert a[0].name == 'str'
    a = jedi.Script(path='module.py', line=7).goto_definitions()
    assert a[0].name == 'str'


@pytest.mark.parametrize("script,name", [
    ("from flask.ext import foo; foo.", "Foo"),  # flask_foo.py
    ("from flask.ext import bar; bar.", "Bar"),  # flaskext/bar.py
    ("from flask.ext import baz; baz.", "Baz"),  # flask_baz/__init__.py
    ("from flask.ext import moo; moo.", "Moo"),  # flaskext/moo/__init__.py
    ("from flask.ext.", "foo"),
    ("from flask.ext.", "bar"),
    ("from flask.ext.", "baz"),
    ("from flask.ext.", "moo"),
    pytest.mark.xfail(("import flask.ext.foo; flask.ext.foo.", "Foo")),
    pytest.mark.xfail(("import flask.ext.bar; flask.ext.bar.", "Foo")),
    pytest.mark.xfail(("import flask.ext.baz; flask.ext.baz.", "Foo")),
    pytest.mark.xfail(("import flask.ext.moo; flask.ext.moo.", "Foo")),
])
def test_flask_ext(script, name):
    """flask.ext.foo is really imported from flaskext.foo or flask_foo.
    """
    path = os.path.join(os.path.dirname(__file__), 'flask-site-packages')
    completions = jedi.Script(script, sys_path=[path]).completions()
    assert name in [c.name for c in completions]


@cwd_at('test/test_evaluate/')
def test_not_importable_file():
    src = 'import not_importable_file as x; x.'
    assert not jedi.Script(src, path='example.py').completions()


def test_import_unique():
    src = "import os; os.path"
    defs = jedi.Script(src, path='example.py').goto_definitions()
    parent_contexts = [d._name._context for d in defs]
    assert len(parent_contexts) == len(set(parent_contexts))


def test_cache_works_with_sys_path_param(tmpdir):
    foo_path = tmpdir.join('foo')
    bar_path = tmpdir.join('bar')
    foo_path.join('module.py').write('foo = 123', ensure=True)
    bar_path.join('module.py').write('bar = 123', ensure=True)
    foo_completions = jedi.Script('import module; module.',
                                  sys_path=[foo_path.strpath]).completions()
    bar_completions = jedi.Script('import module; module.',
                                  sys_path=[bar_path.strpath]).completions()
    assert 'foo' in [c.name for c in foo_completions]
    assert 'bar' not in [c.name for c in foo_completions]

    assert 'bar' in [c.name for c in bar_completions]
    assert 'foo' not in [c.name for c in bar_completions]


def test_import_completion_docstring():
    import abc
    s = jedi.Script('"""test"""\nimport ab')
    completions = s.completions()
    assert len(completions) == 1
    assert completions[0].docstring(fast=False) == abc.__doc__

    # However for performance reasons not all modules are loaded and the
    # docstring is empty in this case.
    assert completions[0].docstring() == ''


def test_goto_definition_on_import():
    assert Script("import sys_blabla", 1, 8).goto_definitions() == []
    assert len(Script("import sys", 1, 8).goto_definitions()) == 1


@cwd_at('jedi')
def test_complete_on_empty_import():
    assert Script("from datetime import").completions()[0].name == 'import'
    # should just list the files in the directory
    assert 10 < len(Script("from .", path='whatever.py').completions()) < 30

    # Global import
    assert len(Script("from . import", 1, 5, 'whatever.py').completions()) > 30
    # relative import
    assert 10 < len(Script("from . import", 1, 6, 'whatever.py').completions()) < 30

    # Global import
    assert len(Script("from . import classes", 1, 5, 'whatever.py').completions()) > 30
    # relative import
    assert 10 < len(Script("from . import classes", 1, 6, 'whatever.py').completions()) < 30

    wanted = set(['ImportError', 'import', 'ImportWarning'])
    assert set([c.name for c in Script("import").completions()]) == wanted
    if not is_py26:  # python 2.6 doesn't always come with a library `import*`.
        assert len(Script("import import", path='').completions()) > 0

    # 111
    assert Script("from datetime import").completions()[0].name == 'import'
    assert Script("from datetime import ").completions()


def test_imports_on_global_namespace_without_path():
    """If the path is None, there shouldn't be any import problem"""
    completions = Script("import operator").completions()
    assert [c.name for c in completions] == ['operator']
    completions = Script("import operator", path='example.py').completions()
    assert [c.name for c in completions] == ['operator']

    # the first one has a path the second doesn't
    completions = Script("import keyword", path='example.py').completions()
    assert [c.name for c in completions] == ['keyword']
    completions = Script("import keyword").completions()
    assert [c.name for c in completions] == ['keyword']


def test_named_import():
    """named import - jedi-vim issue #8"""
    s = "import time as dt"
    assert len(Script(s, 1, 15, '/').goto_definitions()) == 1
    assert len(Script(s, 1, 10, '/').goto_definitions()) == 1


@pytest.mark.skipif('True', reason='The nested import stuff is still very messy.')
def test_goto_following_on_imports():
    s = "import multiprocessing.dummy; multiprocessing.dummy"
    g = Script(s).goto_assignments()
    assert len(g) == 1
    assert (g[0].line, g[0].column) != (0, 0)


def test_os_after_from():
    def check(source, result, column=None):
        completions = Script(source, column=column).completions()
        assert [c.name for c in completions] == result

    check('\nfrom os. ', ['path'])
    check('\nfrom os ', ['import'])
    check('from os ', ['import'])
    check('\nfrom os import whatever', ['import'], len('from os im'))

    check('from os\\\n', ['import'])
    check('from os \\\n', ['import'])


def test_os_issues():
    def import_names(*args, **kwargs):
        return [d.name for d in jedi.Script(*args, **kwargs).completions()]

    # Github issue #759
    s = 'import os, s'
    assert 'sys' in import_names(s)
    assert 'path' not in import_names(s, column=len(s) - 1)
    assert 'os' in import_names(s, column=len(s) - 3)

    # Some more checks
    s = 'from os import path, e'
    assert 'environ' in import_names(s)
    assert 'json' not in import_names(s, column=len(s) - 1)
    assert 'environ' in import_names(s, column=len(s) - 1)
    assert 'path' in import_names(s, column=len(s) - 3)


def test_path_issues():
    """
    See pull request #684 for details.
    """
    source = '''from datetime import '''
    assert jedi.Script(source).completions()
