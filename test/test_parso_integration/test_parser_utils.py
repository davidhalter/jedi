from jedi._compatibility import u, is_py3
from jedi.parser_utils import get_statement_of_position, \
    clean_scope_docstring, safe_literal_eval
from jedi.parser.python import parse
from jedi.parser.python import tree


class TestCallAndName():
    def get_call(self, source):
        # Get the simple_stmt and then the first one.
        simple_stmt = parse(source).children[0]
        return simple_stmt.children[0]

    def test_name_and_call_positions(self):
        name = self.get_call('name\nsomething_else')
        assert name.value == 'name'
        assert name.start_pos == (1, 0)
        assert name.end_pos == (1, 4)

        leaf = self.get_call('1.0\n')
        assert leaf.value == '1.0'
        assert safe_literal_eval(leaf.value) == 1.0
        assert leaf.start_pos == (1, 0)
        assert leaf.end_pos == (1, 3)

    def test_call_type(self):
        call = self.get_call('hello')
        assert isinstance(call, tree.Name)

    def test_literal_type(self):
        literal = self.get_call('1.0')
        assert isinstance(literal, tree.Literal)
        assert type(safe_literal_eval(literal.value)) == float

        literal = self.get_call('1')
        assert isinstance(literal, tree.Literal)
        assert type(safe_literal_eval(literal.value)) == int

        literal = self.get_call('"hello"')
        assert isinstance(literal, tree.Literal)
        assert safe_literal_eval(literal.value) == 'hello'


def test_user_statement_on_import():
    """github #285"""
    s = "from datetime import (\n" \
        "    time)"

    for pos in [(2, 1), (2, 4)]:
        p = parse(s)
        stmt = get_statement_of_position(p, pos)
        assert isinstance(stmt, tree.Import)
        assert [n.value for n in stmt.get_defined_names()] == ['time']


def test_hex_values_in_docstring():
    source = r'''
        def foo(object):
            """
             \xff
            """
            return 1
        '''

    doc = clean_scope_docstring(next(parse(source).iter_funcdefs()))
    if is_py3:
        assert doc == '\xff'
    else:
        assert doc == u('�')
