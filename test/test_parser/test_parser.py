# -*- coding: utf-8 -*-

from jedi._compatibility import u, is_py3
from jedi.parser import Parser, load_grammar
from jedi.parser.user_context import UserContextParser
from jedi.parser import tree as pt
from textwrap import dedent


def test_user_statement_on_import():
    """github #285"""
    s = u("from datetime import (\n"
          "    time)")

    for pos in [(2, 1), (2, 4)]:
        p = UserContextParser(load_grammar(), s, None, pos, None).user_stmt()
        assert isinstance(p, pt.Import)
        assert p.defunct is False
        assert [str(n) for n in p.get_defined_names()] == ['time']


class TestCallAndName():
    def get_call(self, source):
        stmt = Parser(load_grammar(), u(source)).module.statements[0]
        return stmt.expression_list()[0]

    def test_name_and_call_positions(self):
        call = self.get_call('name\nsomething_else')
        assert str(call.name) == 'name'
        assert call.name.start_pos == call.start_pos == (1, 0)
        assert call.name.end_pos == call.end_pos == (1, 4)

        call = self.get_call('1.0\n')
        assert call.value == 1.0
        assert call.start_pos == (1, 0)
        assert call.end_pos == (1, 3)

    def test_call_type(self):
        call = self.get_call('hello')
        assert isinstance(call, pt.Call)
        assert type(call.name) == pt.Name

    def test_literal_type(self):
        literal = self.get_call('1.0')
        assert isinstance(literal, pt.Literal)
        assert type(literal.value) == float

        literal = self.get_call('1')
        assert isinstance(literal, pt.Literal)
        assert type(literal.value) == int

        literal = self.get_call('"hello"')
        assert isinstance(literal, pt.Literal)
        assert literal.value == 'hello'


class TestSubscopes():
    def get_sub(self, source):
        return Parser(load_grammar(), u(source)).module.subscopes[0]

    def test_subscope_names(self):
        name = self.get_sub('class Foo: pass').name
        assert name.start_pos == (1, len('class '))
        assert name.end_pos == (1, len('class Foo'))
        assert str(name) == 'Foo'

        name = self.get_sub('def foo(): pass').name
        assert name.start_pos == (1, len('def '))
        assert name.end_pos == (1, len('def foo'))
        assert str(name) == 'foo'


class TestImports():
    def get_import(self, source):
        return Parser(load_grammar(), source).module.imports[0]

    def test_import_names(self):
        imp = self.get_import(u('import math\n'))
        names = imp.get_defined_names()
        assert len(names) == 1
        assert str(names[0]) == 'math'
        assert names[0].start_pos == (1, len('import '))
        assert names[0].end_pos == (1, len('import math'))

        assert imp.start_pos == (1, 0)
        assert imp.end_pos == (1, len('import math'))


def test_module():
    module = Parser(load_grammar(), u('asdf'), 'example.py').module
    name = module.name
    assert str(name) == 'example'
    assert name.start_pos == (1, 0)
    assert name.end_pos == (1, 7)

    module = Parser(load_grammar(), u('asdf')).module
    name = module.name
    assert str(name) == ''
    assert name.start_pos == (1, 0)
    assert name.end_pos == (1, 0)


def test_end_pos():
    s = u(dedent('''
                 x = ['a', 'b', 'c']
                 def func():
                     y = None
                 '''))
    parser = Parser(load_grammar(), s)
    scope = parser.module.subscopes[0]
    assert scope.start_pos == (3, 0)
    assert scope.end_pos == (5, 0)


def test_carriage_return_statements():
    source = u(dedent('''
        foo = 'ns1!'

        # this is a namespace package
    '''))
    source = source.replace('\n', '\r\n')
    stmt = Parser(load_grammar(), source).module.statements[0]
    assert '#' not in stmt.get_code()


def test_incomplete_list_comprehension():
    """ Shouldn't raise an error, same bug as #418. """
    s = Parser(load_grammar(), u('(1 for def')).module.statements[0]
    assert s.expression_list()


def test_hex_values_in_docstring():
    source = r'''
        def foo(object):
            """
             \xff
            """
            return 1
        '''

    doc = Parser(load_grammar(), dedent(u(source))).module.subscopes[0].raw_doc
    if is_py3:
        assert doc == '\xff'
    else:
        assert doc == u('�')
