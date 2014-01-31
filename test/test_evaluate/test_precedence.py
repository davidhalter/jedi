from jedi.evaluate import precedence


def test_simple():
    p = precedence.create_precedence(iter([1, '+', 2]))
    assert p.left == 1
    assert p.operator == '+'
    assert p.right == 2


def test_invalid():
    """Should just return a simple operation"""
    assert precedence.create_precedence(iter([1, '+'])) == 1
