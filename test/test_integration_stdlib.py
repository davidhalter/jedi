"""
Tests of various stdlib related things that could not be tested
with "Black Box Tests".
"""
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
    source = "import collections\n" + \
             "Person = collections.namedtuple('Person', 'name smart')\n" + \
             "dave = Person('Dave', False)\n" + \
             "dave.%s" % letter
    result = Script(source).completions()
    completions = set(r.name for r in result)
    if is_py26:
        assert completions == set()
    else:
        assert completions == set(expected)


def test_namedtuple_list():
    source = "import collections\n" + \
             "Cat = collections.namedtuple('Person', ['legs', u'length', 'large'])\n" + \
             "garfield = Cat(4, '85cm', True)\n" + \
             "garfield.l"
    result = Script(source).completions()
    completions = set(r.name for r in result)
    if is_py26:
        assert completions == set()
    else:
        assert completions == set(['legs', 'length', 'large'])
