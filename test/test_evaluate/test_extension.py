"""
Test compiled module
"""
import os

import jedi
from ..helpers import cwd_at


def test_completions():
    s = jedi.Script('import _ctypes; _ctypes.')
    assert len(s.completions()) >= 15


def test_call_signatures_extension():
    if os.name == 'nt':
        func = 'LoadLibrary'
        params = 1
    else:
        func = 'dlopen'
        params = 2
    s = jedi.Script('import _ctypes; _ctypes.%s(' % (func,))
    sigs = s.call_signatures()
    assert len(sigs) == 1
    assert len(sigs[0].params) == params


def test_call_signatures_stdlib():
    s = jedi.Script('import math; math.cos(')
    sigs = s.call_signatures()
    assert len(sigs) == 1
    assert len(sigs[0].params) == 1


@cwd_at('test/test_evaluate')
def test_init_extension_module():
    """
    ``__init__`` extension modules are also packages and Jedi should understand
    that.

    Originally coming from #472.
    """
    s = jedi.Script('import init_extension_module as i\ni.', path='not_existing.py')
    assert 'foo' in [c.name for c in s.completions()]

    s = jedi.Script('from init_extension_module import foo\nfoo', path='not_existing.py')
    assert ['foo'] == [c.name for c in s.completions()]
