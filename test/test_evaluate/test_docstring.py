"""
Testing of docstring related issues and especially ``jedi.docstrings``.
"""

from textwrap import dedent
import jedi
from ..helpers import unittest


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
                    :type arg: threading.Thread
                    '''
                    arg."""
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'start' in names

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
