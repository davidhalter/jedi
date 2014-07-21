"""
Test compiled module
"""
import os

import jedi


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
