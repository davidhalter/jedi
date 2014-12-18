"""
Tests of various import related things that could not be tested with "Black Box
Tests".
"""
from jedi import Script
from .helpers import cwd_at
from jedi._compatibility import is_py26

import pytest


def test_goto_definition_on_import():
    assert Script("import sys_blabla", 1, 8).goto_definitions() == []
    assert len(Script("import sys", 1, 8).goto_definitions()) == 1


@cwd_at('jedi')
def test_complete_on_empty_import():
    assert Script("from datetime import").completions()[0].name == 'import'
    # should just list the files in the directory
    assert 10 < len(Script("from .", path='').completions()) < 30

    # Global import
    assert len(Script("from . import", 1, 5, '').completions()) > 30
    # relative import
    assert 10 < len(Script("from . import", 1, 6, '').completions()) < 30

    # Global import
    assert len(Script("from . import classes", 1, 5, '').completions()) > 30
    # relative import
    assert 10 < len(Script("from . import classes", 1, 6, '').completions()) < 30

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


def test_after_from():
    def check(source, result, column=None):
        completions = Script(source, column=column).completions()
        assert [c.name for c in completions] == result

    check('\nfrom os. ', ['path'])
    check('\nfrom os ', ['import'])
    check('from os ', ['import'])
    check('\nfrom os import whatever', ['import'], len('from os im'))

    check('from os\\\n', ['import'])
    check('from os \\\n', ['import'])
