"""
Testing of docstring related issues and especially ``jedi.docstrings``.
"""

from textwrap import dedent
import jedi
from ..helpers import unittest

try:
    import numpydoc
except ImportError:
    numpydoc_unavailable = True
else:
    numpydoc_unavailable = False


class TestDocstring(unittest.TestCase):
    def test_function_doc(self):
        defs = jedi.Script("""
        def func():
            '''Docstring of `func`.'''
        func""").goto_definitions()
        self.assertEqual(defs[0].raw_doc, 'Docstring of `func`.')

    @unittest.skip('need evaluator class for that')
    def test_attribute_docstring(self):
        defs = jedi.Script("""
        x = None
        '''Docstring of `x`.'''
        x""").goto_definitions()
        self.assertEqual(defs[0].raw_doc, 'Docstring of `x`.')

    @unittest.skip('need evaluator class for that')
    def test_multiple_docstrings(self):
        defs = jedi.Script("""
        def func():
            '''Original docstring.'''
        x = func
        '''Docstring of `x`.'''
        x""").goto_definitions()
        docs = [d.raw_doc for d in defs]
        self.assertEqual(docs, ['Original docstring.', 'Docstring of `x`.'])

    def test_completion(self):
        assert jedi.Script('''
        class DocstringCompletion():
            #? []
            """ asdfas """''').completions()

    def test_docstrings_type_dotted_import(self):
        s = """
                def func(arg):
                    '''
                    :type arg: random.Random
                    '''
                    arg."""
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'seed' in names

    def test_docstrings_param_type(self):
        s = """
                def func(arg):
                    '''
                    :param str arg: some description
                    '''
                    arg."""
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'join' in names

    def test_docstrings_type_str(self):
        s = """
                def func(arg):
                    '''
                    :type arg: str
                    '''
                    arg."""

        names = [c.name for c in jedi.Script(s).completions()]
        assert 'join' in names

    def test_docstring_instance(self):
        # The types hint that it's a certain kind
        s = dedent("""
            class A:
                def __init__(self,a):
                    '''
                    :type a: threading.Thread
                    '''

                    if a is not None:
                        a.start()

                    self.a = a


            def method_b(c):
                '''
                :type c: A
                '''

                c.""")

        names = [c.name for c in jedi.Script(s).completions()]
        assert 'a' in names
        assert '__init__' in names
        assert 'mro' not in names  # Exists only for types.

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpydoc_docstring(self):
        s = dedent('''
        def foobar(x, y):
            """
            Parameters
            ----------
            x : int
            y : str
            """
            y.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpydoc_docstring_set_of_values(self):
        s = dedent('''
        def foobar(x, y):
            """
            Parameters
            ----------
            x : {'foo', 'bar', 100500}, optional
            """
            x.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names
        assert 'numerator' in names

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpydoc_alternative_types(self):
        s = dedent('''
        def foobar(x, y):
            """
            Parameters
            ----------
            x : int or str or list
            """
            x.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names
        assert 'numerator' in names
        assert 'append' in names
