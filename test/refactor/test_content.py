from jedi.refactoring import Content, Pos, PosRange
from pytest import fixture


@fixture
def content():
    full_lines = ['abc', 'def']
    return Content(full_lines)


def test_getitem(content):
    pr = PosRange(Pos(1, 0), Pos(2, 3))
    assert content[pr] == content.lines
    pr = PosRange(Pos(1, 0), Pos(1, 2))
    assert content[pr] == ['ab']
    pr = PosRange(Pos(2, 1), Pos(2, 3))
    assert content[pr] == ['ef']


def test_delete_all(content):
    pr = PosRange(Pos(1, 0), Pos(2, 3))
    del content[pr]
    assert content.lines == []


def test_delete_range(content):
    pr = PosRange(Pos(1, 1), Pos(2, 2))
    del content[pr]
    assert content.lines == ['af']


def test_delete_range_whole_line(content):
    pr = PosRange(Pos(1, 1), Pos(2, 3))
    del content[pr]
    assert content.lines == ['a']


def test_delete_one_line(content):
    pr = PosRange(Pos(1, 0), Pos(1, 3))
    del content[pr]
    assert content.lines == ['def']


def test_setitem_multiline(content):
    pr = PosRange(Pos(1, 1), Pos(2, 2))
    new_value = 'baaaz'
    content[pr] = new_value
    assert content.lines == ['a' + new_value + 'f']


def test_setitem_one_line(content):
    pr = PosRange(Pos(1, 1), Pos(1, 3))
    new_value = 'baaaz'
    content[pr] = new_value
    assert content.lines == ['a' + new_value, 'def']

