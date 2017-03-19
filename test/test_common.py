from jedi.common import splitlines


def test_splitlines_no_keepends():
    assert splitlines('asd\r\n') == ['asd', '']
    assert splitlines('asd\r\n\f') == ['asd', '\f']
    assert splitlines('\fasd\r\n') == ['\fasd', '']
    assert splitlines('') == ['']
    assert splitlines('\n') == ['', '']


def test_splitlines_keepends():
    assert splitlines('asd\r\n', keepends=True) == ['asd\r\n', '']
    assert splitlines('asd\r\n\f', keepends=True) == ['asd\r\n', '\f']
    assert splitlines('\fasd\r\n', keepends=True) == ['\fasd\r\n', '']
    assert splitlines('', keepends=True) == ['']
    assert splitlines('\n', keepends=True) == ['\n', '']
