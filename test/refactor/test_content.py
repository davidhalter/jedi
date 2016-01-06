from jedi.refactoring import Content, Position, PosRange
from pytest import fixture


@fixture
def content():
    full_lines = ['abc', 'def']
    return Content(full_lines)


def test_getitem(content):
    pr = PosRange(Position(1, 0), Position(2, 3))
    assert content[pr] == content.lines
    pr = PosRange(Position(1, 0), Position(1, 2))
    assert content[pr] == ['ab']
    pr = PosRange(Position(2, 1), Position(2, 3))
    assert content[pr] == ['ef']


def test_delete_all(content):
    pr = PosRange(Position(1, 0), Position(2, 3))
    del content[pr]
    assert content.lines == []


def test_delete_range(content):
    pr = PosRange(Position(1, 1), Position(2, 2))
    del content[pr]
    assert content.lines == ['af']


def test_delete_range_whole_line(content):
    pr = PosRange(Position(1, 1), Position(2, 3))
    del content[pr]
    assert content.lines == ['a']


def test_delete_one_line(content):
    pr = PosRange(Position(1, 0), Position(1, 3))
    del content[pr]
    assert content.lines == ['def']


def test_setitem_multiline(content):
    pr = PosRange(Position(1, 1), Position(2, 2))
    new_value = 'baaaz'
    content[pr] = new_value
    assert content.lines == ['a' + new_value + 'f']


def test_setitem_one_line(content):
    pr = PosRange(Position(1, 1), Position(1, 3))
    new_value = 'baaaz'
    content[pr] = new_value
    assert content.lines == ['a' + new_value, 'def']

