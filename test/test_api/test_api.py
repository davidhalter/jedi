"""
Test all things related to the ``jedi.api`` module.
"""

from textwrap import dedent

from jedi import api
from jedi._compatibility import is_py3
from pytest import raises
from jedi.parser import utils


def test_preload_modules():
    def check_loaded(*modules):
        # +1 for None module (currently used)
        assert len(parser_cache) == len(modules) + 1
        for i in modules:
            assert [i in k for k in parser_cache.keys() if k is not None]

    temp_cache, utils.parser_cache = utils.parser_cache, {}
    parser_cache = utils.parser_cache

    api.preload_module('sys')
    check_loaded()  # compiled (c_builtin) modules shouldn't be in the cache.
    api.preload_module('json', 'token')
    check_loaded('json', 'token')

    utils.parser_cache = temp_cache


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


def _check_number(source, result='float'):
    completions = api.Script(source).completions()
    assert completions[0].parent().name == result


def test_completion_on_number_literals():
    # No completions on an int literal (is a float).
    assert [c.name for c in api.Script('1.').completions()] \
        == ['and', 'if', 'in', 'is', 'not', 'or']

    # Multiple points after an int literal basically mean that there's a float
    # and a call after that.
    _check_number('1..')
    _check_number('1.0.')

    # power notation
    _check_number('1.e14.')
    _check_number('1.e-3.')
    _check_number('9e3.')
    assert api.Script('1.e3..').completions() == []
    assert api.Script('1.e-13..').completions() == []


def test_completion_on_hex_literals():
    assert api.Script('0x1..').completions() == []
    _check_number('0x1.', 'int')  # hexdecimal
    # Completing binary literals doesn't work if they are not actually binary
    # (invalid statements).
    assert api.Script('0b2.b').completions() == []
    _check_number('0b1.', 'int')  # binary

    _check_number('0x2e.', 'int')
    _check_number('0xE7.', 'int')
    _check_number('0xEa.', 'int')
    # theoretically, but people can just check for syntax errors:
    #assert api.Script('0x.').completions() == []


def test_completion_on_complex_literals():
    assert api.Script('1j..').completions() == []
    _check_number('1j.', 'complex')
    _check_number('44.j.', 'complex')
    _check_number('4.0j.', 'complex')
    # No dot no completion - I thought, but 4j is actually a literall after
    # which a keyword like or is allowed. Good times, haha!
    assert (set([c.name for c in api.Script('4j').completions()]) ==
            set(['if', 'and', 'in', 'is', 'not', 'or']))


def test_goto_assignments_on_non_name():
    assert api.Script('for').goto_assignments() == []

    assert api.Script('assert').goto_assignments() == []
    if is_py3:
        assert api.Script('True').goto_assignments() == []
    else:
        # In Python 2.7 True is still a name.
        assert api.Script('True').goto_assignments()[0].description == 'class bool'


def test_goto_definitions_on_non_name():
    assert api.Script('import x', column=0).goto_definitions() == []


def test_goto_definition_not_multiple():
    """
    There should be only one Definition result if it leads back to the same
    origin (e.g. instance method)
    """

    s = dedent('''\
            import random
            class A():
                def __init__(self, a):
                    self.a = 3

                def foo(self):
                    pass

            if random.randint(0, 1):
                a = A(2)
            else:
                a = A(1)
            a''')
    assert len(api.Script(s).goto_definitions()) == 1


def test_usage_description():
    descs = [u.description for u in api.Script("foo = ''; foo").usages()]
    assert set(descs) == set(["foo = ''", 'foo'])


def test_get_line_code():
    def get_line_code(source, line=None, **kwargs):
        return api.Script(source, line=line).completions()[0].get_line_code(**kwargs)

    # On builtin
    assert get_line_code('') == ''

    # On custom code
    line = '    foo'
    assert get_line_code('def foo():\n%s' % line) == line

    # With before/after
    line = '    foo'
    source = 'def foo():\n%s\nother_line' % line
    assert get_line_code(source, line=2) == line
    assert get_line_code(source, line=2, after=1) == line + '\nother_line'
    assert get_line_code(source, line=2, after=1, before=1) == source


def test_goto_assignments_follow_imports():
    code = dedent("""
    import inspect
    inspect.isfunction""")
    definition, = api.Script(code, column=0).goto_assignments(follow_imports=True)
    assert 'inspect.py' in definition.module_path
    assert definition.start_pos == (1, 0)

    definition, = api.Script(code).goto_assignments(follow_imports=True)
    assert 'inspect.py' in definition.module_path
    assert definition.start_pos > (1, 0)
