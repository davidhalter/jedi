from jedi.parser import Parser
from jedi.evaluate import precedence


def parse_tree(statement_string):
    p = Parser(statement_string, no_docstr=True)
    stmt = p.module.statements[0]
    iterable = iter(stmt.expression_list())
    pr = precedence.create_precedence(iterable)
    if isinstance(pr, precedence.Precedence):
        return pr.parse_tree(strip_literals=True)
    else:
        try:
            return pr.value  # Literal
        except AttributeError:
            return pr


def test_simple():
    assert parse_tree('1+2') == (1, '+', 2)
    assert parse_tree('+2') == (None, '+', 2)


def test_invalid():
    """Should just return a simple operation."""
    assert parse_tree('1 +') == 1
    assert parse_tree('+') is None

    assert parse_tree('* 1') == 1
