import os
import sys

import pytest

import jedi
from jedi._compatibility import find_module_py33
from ..helpers import cwd_at


@pytest.mark.skipif('sys.version_info < (3,3)')
def test_find_module_py33():
    """Needs to work like the old find_module."""
    assert find_module_py33('_io') == (None, '_io', False)


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
    defs = [d._definition for d in defs]
    assert len(defs) == len(set(defs))


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
