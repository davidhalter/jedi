# -*- coding: utf-8 -*-
import sys
from textwrap import dedent

import pytest

from jedi._compatibility import u, is_py3
from jedi.parser.python import parse, load_grammar
from jedi.parser.python import tree
from jedi.common import splitlines


def test_basic_parsing():
    def compare(string):
        """Generates the AST object and then regenerates the code."""
        assert parse(string).get_code() == string

    compare('\na #pass\n')
    compare('wblabla* 1\t\n')
    compare('def x(a, b:3): pass\n')
    compare('assert foo\n')


class TestSubscopes():
    def get_sub(self, source):
        return parse(source).children[0]

    def test_subscope_names(self):
        name = self.get_sub('class Foo: pass').name
        assert name.start_pos == (1, len('class '))
        assert name.end_pos == (1, len('class Foo'))
        assert name.value == 'Foo'

        name = self.get_sub('def foo(): pass').name
        assert name.start_pos == (1, len('def '))
        assert name.end_pos == (1, len('def foo'))
        assert name.value == 'foo'


class TestImports():
    def get_import(self, source):
        return next(parse(source).iter_imports())

    def test_import_names(self):
        imp = self.get_import(u('import math\n'))
        names = imp.get_defined_names()
        assert len(names) == 1
        assert names[0].value == 'math'
        assert names[0].start_pos == (1, len('import '))
        assert names[0].end_pos == (1, len('import math'))

        assert imp.start_pos == (1, 0)
        assert imp.end_pos == (1, len('import math'))


def test_end_pos():
    s = dedent('''
               x = ['a', 'b', 'c']
               def func():
                   y = None
               ''')
    parser = parse(s)
    scope = next(parser.iter_funcdefs())
    assert scope.start_pos == (3, 0)
    assert scope.end_pos == (5, 0)


def test_carriage_return_statements():
    source = dedent('''
        foo = 'ns1!'

        # this is a namespace package
    ''')
    source = source.replace('\n', '\r\n')
    stmt = parse(source).children[0]
    assert '#' not in stmt.get_code()


def test_incomplete_list_comprehension():
    """ Shouldn't raise an error, same bug as #418. """
    # With the old parser this actually returned a statement. With the new
    # parser only valid statements generate one.
    children = parse('(1 for def').children
    assert [c.type for c in children] == \
        ['error_node', 'error_node', 'newline', 'endmarker']


def test_newline_positions():
    endmarker = parse('a\n').children[-1]
    assert endmarker.end_pos == (2, 0)
    new_line = endmarker.get_previous_leaf()
    assert new_line.start_pos == (1, 1)
    assert new_line.end_pos == (2, 0)


def test_end_pos_error_correction():
    """
    Source code without ending newline are given one, because the Python
    grammar needs it. However, they are removed again. We still want the right
    end_pos, even if something breaks in the parser (error correction).
    """
    s = 'def x():\n .'
    m = parse(s)
    func = m.children[0]
    assert func.type == 'funcdef'
    assert func.end_pos == (2, 2)
    assert m.end_pos == (2, 2)


def test_param_splitting():
    """
    Jedi splits parameters into params, this is not what the grammar does,
    but Jedi does this to simplify argument parsing.
    """
    def check(src, result):
        # Python 2 tuple params should be ignored for now.
        grammar = load_grammar('%s.%s' % sys.version_info[:2])
        m = parse(src, grammar=grammar)
        if is_py3:
            assert not list(m.iter_funcdefs())
        else:
            # We don't want b and c to be a part of the param enumeration. Just
            # ignore them, because it's not what we want to support in the
            # future.
            assert [param.name.value for param in next(m.iter_funcdefs()).params] == result

    check('def x(a, (b, c)):\n pass', ['a'])
    check('def x((b, c)):\n pass', [])


def test_unicode_string():
    s = tree.String(None, u('bö'), (0, 0))
    assert repr(s)  # Should not raise an Error!


def test_backslash_dos_style():
    assert parse('\\\r\n')


def test_started_lambda_stmt():
    m = parse(u'lambda a, b: a i')
    assert m.children[0].type == 'error_node'


def test_python2_octal():
    module = parse('0660')
    first = module.children[0]
    if is_py3:
        assert first.type == 'error_node'
    else:
        assert first.children[0].type == 'number'


def test_python3_octal():
    module = parse('0o660')
    if is_py3:
        assert module.children[0].children[0].type == 'number'
    else:
        assert module.children[0].type == 'error_node'


def test_load_newer_grammar():
    # This version shouldn't be out for a while, but if we somehow get this it
    # should just take the latest Python grammar.
    load_grammar('15.8')
    # The same is true for very old grammars (even though this is probably not
    # going to be an issue.
    load_grammar('1.5')


@pytest.mark.parametrize('code', ['foo "', 'foo """\n', 'foo """\nbar'])
def test_open_string_literal(code):
    """
    Testing mostly if removing the last newline works.
    """
    lines = splitlines(code, keepends=True)
    end_pos = (len(lines), len(lines[-1]))
    module = parse(code)
    assert module.get_code() == code
    assert module.end_pos == end_pos == module.children[1].end_pos
