"""
Tests of various stdlib related things that could not be tested
with "Black Box Tests".
"""
from textwrap import dedent

import pytest


@pytest.mark.parametrize('definition, expected', [
    ('class accessor(property):\n    pass', 'str'),
    ('class accessor(property):\n    fget = None', 'str'),
    ('class base(property):\n    pass\nclass accessor(base):\n    pass', 'str'),
    ('class accessor(property):\n'
     '    def __get__(self, instance, owner):\n'
     '        return self.fget(instance)', 'str'),
    ('class accessor(property):\n'
     '    def __get__(self, instance, owner):\n'
     '        return 42', 'int'),
    ('class accessor(property):\n'
     '    def __get__(self, instance, owner) -> int:\n'
     '        return self.fget(instance)', 'int'),
])
def test_property_subclass(definition, expected, Script):
    source = definition + '\n' + dedent('''\
        class Example:
            @accessor
            def value(self):
                return 'text'
        Example().value''')
    assert {v.name for v in Script(source).infer()} == {expected}
    if expected == 'str':
        assert [c.name for c in Script(source + '.upp').complete()] == ['upper']


@pytest.mark.parametrize('arguments', ['getter', 'fget=getter', 'fset=None, fget=getter'])
def test_property_subclass_fget(arguments, Script):
    source = dedent('''\
        class accessor(property):
            pass
        def getter(obj):
            return obj
        descriptor = accessor(%s)
        ''') % arguments
    assert [v.name for v in Script(source + 'descriptor.fget').infer()] == ['getter']
    assert [v.name for v in Script(source + "descriptor.fget('text')").infer()] == ['str']


def test_property_subclass_class_access(Script):
    source = dedent('''\
        class accessor(property):
            pass
        class Example:
            @accessor
            def value(self):
                return 'text'
        ''')
    assert [v.name for v in Script(source + 'Example.value').infer()] == ['accessor']
    assert [v.name for v in Script(source + 'Example.value.fget').infer()] == ['value']
    assert [v.name for v in Script(source + 'accessor().fget').infer()] == ['NoneType']


def test_property_conditional_override(Script):
    source = dedent('''\
        import os
        from typing import Any
        class sphinx_accessor(property):
            def __get__(self, instance: Any, cls: type) -> Any:
                try:
                    return self.fget(instance if isinstance(instance, cls) else cls)
                except (AttributeError, ImportError):
                    return self
        BUILDING_SPHINX_DOCS = 'SPHINX_BUILD' in os.environ
        if BUILDING_SPHINX_DOCS:
            property = sphinx_accessor
        class Example:
            @property
            def value(self):
                return 'text'
        Example().value''')
    assert [c.name for c in Script(source + '.upp').complete()] == ['upper']


@pytest.mark.parametrize(['letter', 'expected'], [
    ('n', ['name']),
    ('s', ['smart']),
])
def test_namedtuple_str(letter, expected, Script):
    source = dedent("""\
        import collections
        Person = collections.namedtuple('Person', 'name smart')
        dave = Person('Dave', False)
        dave.%s""") % letter
    result = Script(source).complete()
    completions = set(r.name for r in result)
    assert completions == set(expected)


def test_namedtuple_list(Script):
    source = dedent("""\
        import collections
        Cat = collections.namedtuple('Person', ['legs', u'length', 'large'])
        garfield = Cat(4, '85cm', True)
        garfield.l""")
    result = Script(source).complete()
    completions = set(r.name for r in result)
    assert completions == {'legs', 'length', 'large'}


def test_namedtuple_content(Script):
    source = dedent("""\
        import collections
        Foo = collections.namedtuple('Foo', ['bar', 'baz'])
        named = Foo(baz=4, bar=3.0)
        unnamed = Foo(4, '')
        """)

    def d(source):
        x, = Script(source).infer()
        return x.name

    assert d(source + 'unnamed.bar') == 'int'
    assert d(source + 'unnamed.baz') == 'str'
    assert d(source + 'named.bar') == 'float'
    assert d(source + 'named.baz') == 'int'


def test_nested_namedtuples(Script):
    """
    From issue #730.
    """
    s = Script(dedent('''
        import collections
        Dataset = collections.namedtuple('Dataset', ['data'])
        Datasets = collections.namedtuple('Datasets', ['train'])
        train_x = Datasets(train=Dataset('data_value'))
        train_x.train.'''))
    assert 'data' in [c.name for c in s.complete()]


def test_namedtuple_infer(Script):
    source = dedent("""
        from collections import namedtuple

        Foo = namedtuple('Foo', 'id timestamp gps_timestamp attributes')
        Foo""")

    from jedi.api import Script

    d1, = Script(source).infer()

    assert d1.get_line_code() == "class Foo(tuple):\n"
    assert d1.module_path is None
    assert d1.docstring() == 'Foo(id, timestamp, gps_timestamp, attributes)'


def test_re_sub(Script, environment):
    """
    This whole test was taken out of completion/stdlib.py, because of the
    version differences.
    """
    def run(code):
        defs = Script(code).infer()
        return {d.name for d in defs}

    names = run("import re; re.sub('a', 'a', 'f')")
    assert names == {'str'}

    # This param is missing because of overloading.
    names = run("import re; re.sub('a', 'a')")
    assert names == {'str', 'bytes'}
