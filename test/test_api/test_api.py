"""
Test all things related to the ``jedi.api`` module.
"""

from jedi import api
from pytest import raises


def test_preload_modules():
    def check_loaded(*modules):
        # +1 for None module (currently used)
        assert len(parser_cache) == len(modules) + 1
        for i in modules:
            assert [i in k for k in parser_cache.keys() if k is not None]

    from jedi import cache
    temp_cache, cache.parser_cache = cache.parser_cache, {}
    parser_cache = cache.parser_cache

    api.preload_module('sys')
    check_loaded()  # compiled (c_builtin) modules shouldn't be in the cache.
    api.preload_module('json', 'token')
    check_loaded('json', 'token')

    cache.parser_cache = temp_cache


def test_empty_script():
    assert api.Script('')


def test_line_number_errors():
    """
    Script should raise a ValueError if line/column numbers are not in a
    valid range.
    """
    s = 'hello'
    # lines
    with raises(ValueError):
        api.Script(s, 2, 0)
    with raises(ValueError):
        api.Script(s, 0, 0)

    # columns
    with raises(ValueError):
        api.Script(s, 1, len(s) + 1)
    with raises(ValueError):
        api.Script(s, 1, -1)

    # ok
    api.Script(s, 1, 0)
    api.Script(s, 1, len(s))


def test_completion_on_int_literals():
    # No completions on an int literal (is a float).
    assert api.Script('1.').completions() == []

    # Multiple points after an int literal basically mean that there's a float
    # and a call after that.
    #assert api.Script('1..').completions()[0].parent().name == 'float'
    assert api.Script('1..').completions()[0]._definition.parent.name == 'float'
    assert api.Script('1.0.').completions()[0]._definition.parent.name == 'float'
