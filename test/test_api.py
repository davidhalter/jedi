"""
Test all things related to the ``jedi.api`` module.
"""

from jedi import common, api
from pytest import raises


def test_preload_modules():
    def check_loaded(*modules):
        # + 1 for builtin, +1 for None module (currently used)
        assert len(new) == len(modules) + 2
        for i in modules + ('__builtin__',):
            assert [i in k for k in new.keys() if k is not None]

    from jedi import cache
    temp_cache, cache.parser_cache = cache.parser_cache, {}
    new = cache.parser_cache
    with common.ignored(KeyError): # performance of tests -> no reload
        new['__builtin__'] = temp_cache['__builtin__']

    api.preload_module('datetime')
    check_loaded('datetime')
    api.preload_module('json', 'token')
    check_loaded('datetime', 'json', 'token')

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
