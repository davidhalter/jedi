from textwrap import dedent

import jedi
from jedi._compatibility import u
from jedi import cache
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
    p = FastParser(source)
    assert [str(n) for n in p.module.get_defined_names()] == ['Foo']


def test_change_and_undo():

    def fp(src):
        p = FastParser(u(src))
        cache.save_parser(None, None, p, pickling=False)

        # TODO Don't change get_code, the whole thing should be the same.
        # -> Need to refactor the parser first, though.
        assert src == p.module.get_code()[:-1]

    cache.parser_cache.pop(None, None)
    func_before = 'def func():\n    pass\n'
    fp(func_before + 'a')
    fp(func_before + 'b')
    fp(func_before + 'a')

    cache.parser_cache.pop(None, None)
    fp('a')
    fp('b')
    fp('a')
