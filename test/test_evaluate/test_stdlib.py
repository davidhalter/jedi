"""
Tests of various stdlib related things that could not be tested
with "Black Box Tests".
"""
from textwrap import dedent

import pytest
from jedi import Script
from jedi._compatibility import is_py26

# The namedtuple is different for different Python2.7 versions. Some versions
# are missing the attribute `_class_template`.
pytestmark = pytest.mark.skipif('sys.version_info[0] < 3')


@pytest.mark.parametrize(['letter', 'expected'], [
    ('n', ['name']),
    ('s', ['smart']),
])
def test_namedtuple_str(letter, expected):
    source = dedent("""\
        import collections
        Person = collections.namedtuple('Person', 'name smart')
        dave = Person('Dave', False)
        dave.%s""") % letter
    result = Script(source).completions()
    completions = set(r.name for r in result)
    if is_py26:
        assert completions == set()
    else:
        assert completions == set(expected)


def test_namedtuple_list():
    source = dedent("""\
        import collections
        Cat = collections.namedtuple('Person', ['legs', u'length', 'large'])
        garfield = Cat(4, '85cm', True)
        garfield.l""")
    result = Script(source).completions()
    completions = set(r.name for r in result)
    if is_py26:
        assert completions == set()
    else:
        assert completions == set(['legs', 'length', 'large'])


def test_namedtuple_content():
    source = dedent("""\
        import collections
        Foo = collections.namedtuple('Foo', ['bar', 'baz'])
        named = Foo(baz=4, bar=3.0)
        unnamed = Foo(4, '')
        """)

    def d(source):
        x, = Script(source).goto_definitions()
        return x.name

    assert d(source + 'unnamed.bar') == 'int'
    assert d(source + 'unnamed.baz') == 'str'
    assert d(source + 'named.bar') == 'float'
    assert d(source + 'named.baz') == 'int'


def test_nested_namedtuples():
    """
    From issue #730.
    """
    s = Script(dedent('''
        import collections
        Dataset = collections.namedtuple('Dataset', ['data'])
        Datasets = collections.namedtuple('Datasets', ['train'])
        train_x = Datasets(train=Dataset('data_value'))
        train_x.train.'''
    ))
    assert 'data' in [c.name for c in s.completions()]
