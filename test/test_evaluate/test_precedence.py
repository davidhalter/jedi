import pytest

from jedi.evaluate import precedence
cp = lambda *args: precedence.create_precedence(iter(args))


@pytest.skip('sorry precedence stuff is still not implemented yet')
def test_simple():
    p = cp(1, '+', 2)
    assert p.left == 1
    assert p.operator == '+'
    assert p.right == 2

    p = cp('+', 2)
    assert p.left is None
    assert p.operator == '+'
    assert p.right == 2


@pytest.skip('sorry precedence stuff is still not implemented yet')
def test_invalid():
    """Should just return a simple operation."""
    assert cp(1, '+') == 1
    assert cp('+') is None

    assert cp('*', 1) == 1
