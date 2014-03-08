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
    assert parse_tree('1+2-3') == ((1, '+', 2), '-', 3)


def test_prefixed():
    assert parse_tree('--2') == (None, '-', (None, '-', 2))
    assert parse_tree('1 and not - 2') == (1, 'and', (None, '-', 2))


def test_invalid():
    """Should just return a simple operation."""
    assert parse_tree('1 +') == 1
    assert parse_tree('+') is None

    assert parse_tree('* 1') == 1
    assert parse_tree('1 * * 1') == (1, '*', 1)

    # invalid operator
    assert parse_tree('1 not - 1') == (1, '-', 1)
    assert parse_tree('1 - not ~1') == (1, '-', (None, '~', 1))

    # not not allowed
    assert parse_tree('1 is not not 1') == (1, 'is not', 1)


def test_multi_part():
    assert parse_tree('1 not in 2') == (1, 'not in', 2)
    assert parse_tree('1 is not -1') == (1, 'is not', (None, '-', 1))
    assert parse_tree('1 is 1') == (1, 'is', 1)


def test_power():
    assert parse_tree('2 ** 3 ** 4') == (2, '**', (3, '**', 4))
