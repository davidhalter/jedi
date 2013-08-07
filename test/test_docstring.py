import jedi
from .base import unittest


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
