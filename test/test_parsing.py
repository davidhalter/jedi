from jedi.parsing import Parser
from jedi import parsing_representation as pr

def test_user_statement_on_import():
    """github #285"""
    s = "from datetime import (\n" \
        "    time)"

    for pos in [(2, 1), (2, 4)]:
        u = Parser(s, user_position=pos).user_stmt
        assert isinstance(u, pr.Import)
        assert u.defunct == False
        assert [str(n) for n in u.get_defined_names()] == ['time']


class TestCallAndName():
    def get_call(self, source):
        stmt = Parser(source, no_docstr=True).module.statements[0]
        return stmt.get_commands()[0]

    def test_name_and_call_positions(self):
        call = self.get_call('name\nsomething_else')
        assert str(call.name) == 'name'
        assert call.name.start_pos == call.start_pos == (1, 0)
        assert call.name.end_pos == call.end_pos == (1, 4)

        call = self.get_call('1.0\n')
        assert call.name == 1.0
        assert call.name.start_pos == call.start_pos == (1, 0)
        assert call.name.end_pos == call.end_pos == (1, 3)

    def test_call_type(self):
        call = self.get_call('hello')
        assert call.type == pr.Call.NAME
        assert type(call.name) == pr.Name

        call = self.get_call('1.0')
        assert type(call.name) == float
        assert call.type == pr.Call.NUMBER
        call = self.get_call('1')
        assert type(call.name) == int
        assert call.type == pr.Call.NUMBER

        call = self.get_call('"hello"')
        assert call.type == pr.Call.STRING
        assert call.name == 'hello'

def test_module():
    module = Parser('asdf', 'example.py', no_docstr=True).module
    name = module.name
    assert str(name) == 'example'
    assert name.start_pos == (0, 0)
    assert name.end_pos == (0, 0)

    module = Parser('asdf', no_docstr=True).module
    name = module.name
    assert str(name) == ''
    assert name.start_pos == (0, 0)
    assert name.end_pos == (0, 0)
