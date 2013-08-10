from jedi import parsing
from jedi import parsing_representation as pr

def test_user_statement_on_import():
    """github #285"""
    s = "from datetime import (\n" \
        "    time)"

    for pos in [(2, 1), (2, 4)]:
        u = parsing.Parser(s, user_position=pos).user_stmt
        assert isinstance(u, pr.Import)
        assert u.defunct == False
        assert [str(n) for n in u.get_defined_names()] == ['time']
