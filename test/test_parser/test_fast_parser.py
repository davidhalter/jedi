from textwrap import dedent

import jedi
from jedi._compatibility import u
from jedi import cache
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser


def test_add_to_end():
    """
    fast_parser doesn't parse everything again. It just updates with the
    help of caches, this is an example that didn't work.
    """

    a = """
class Abc():
    def abc(self):
        self.x = 3

class Two(Abc):
    def h(self):
        self
"""  #      ^ here is the first completion

    b = "    def g(self):\n" \
        "        self."
    assert jedi.Script(a, 8, 12, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()

    a = a[:-1] + '.\n'
    assert jedi.Script(a, 8, 13, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()


def test_class_in_docstr():
    """
    Regression test for a problem with classes in docstrings.
    """
    a = '"\nclasses\n"'
    jedi.Script(a, 1, 0)._parser

    b = a + '\nimport os'
    assert jedi.Script(b, 4, 8).goto_assignments()


def test_carriage_return_splitting():
    source = u(dedent('''



        "string"

        class Foo():
            pass
        '''))
    source = source.replace('\n', '\r\n')
    p = FastParser(load_grammar(), source)
    assert [n.value for lst in p.module.names_dict.values() for n in lst] == ['Foo']


def test_change_and_undo():

    def fp(src, number_parsers_used):
        p = FastParser(load_grammar(), u(src))
        cache.save_parser(None, None, p, pickling=False)

        # TODO Don't change get_code, the whole thing should be the same.
        # -> Need to refactor the parser first, though.
        assert src == p.module.get_code()[:-1]
        assert p.number_parsers_used == number_parsers_used

    cache.parser_cache.pop(None, None)
    func_before = 'def func():\n    pass\n'
    # Parse the function and a.
    fp(func_before + 'a', 2)
    # Parse just b.
    fp(func_before + 'b', 1)
    # b has changed to a again, so parse that.
    fp(func_before + 'a', 1)
    # Same as before no parsers should be used.
    fp(func_before + 'a', 0)

    # Getting rid of an old parser: Still no parsers used.
    fp('a', 0)
    # Now the file has completely change and we need to parse.
    fp('b', 1)
    # And again.
    fp('a', 1)


def test_incomplete_function():
    source = '''return ImportErr'''

    script = jedi.Script(dedent(source), 1, 3)
    assert script.completions()
