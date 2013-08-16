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


def test_name_and_call_positions():
    stmt = Parser('name\nsomething_else').module.statements[0]
    call = stmt.get_commands()[0]
    name = call.name
    print call, name
    assert str(name) == 'name'
    assert name.start_pos == call.start_pos == (1, 0)
    assert name.end_pos == call.end_pos == (1, 4)
