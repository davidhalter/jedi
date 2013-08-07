"""
Tests of various import related things that could not be tested with "Black Box
Tests".
"""

import itertools

from jedi import Script
from .helpers import cwd_at


def test_goto_definition_on_import():
    assert Script("import sys_blabla", 1, 8).goto_definitions() == []
    assert len(Script("import sys", 1, 8).goto_definitions()) == 1


@cwd_at('jedi')
def test_complete_on_empty_import():
    # should just list the files in the directory
    assert 10 < len(Script("from .", source_path='').completions()) < 30
    assert 10 < len(Script("from . import", 1, 5, '').completions()) < 30
    assert 10 < len(Script("from . import classes", 1, 5, '').completions()) < 30
    assert len(Script("import").completions()) == 0
    assert len(Script("import import", source_path='').completions()) > 0

    # 111
    assert Script("from datetime import").completions()[0].name == 'import'
    assert Script("from datetime import ").completions()


def test_named_import():
    """named import - jedi-vim issue #8"""
    s = "import time as dt"
    assert len(Script(s, 1, 15, '/').goto_definitions()) == 1
    assert len(Script(s, 1, 10, '/').goto_definitions()) == 1


def test_goto_following_on_imports():
    s = "import multiprocessing.dummy; multiprocessing.dummy"
    g = Script(s).goto_assignments()
    assert len(g) == 1
    assert g[0].start_pos != (0, 0)


def test_follow_definition():
    """ github issue #45 """
    c = Script("from datetime import timedelta; timedelta").completions()
    # type can also point to import, but there will be additional
    # attributes
    objs = itertools.chain.from_iterable(r.follow_definition() for r in c)
    types = [o.type for o in objs]
    assert 'import' not in types and 'class' in types
