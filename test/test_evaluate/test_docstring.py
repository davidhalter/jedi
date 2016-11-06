"""
Testing of docstring related issues and especially ``jedi.docstrings``.

CommandLine:
    # Switch to the right directory
    cd $(python -c "import jedi; from os.path import dirname, abspath; print(dirname(dirname(abspath(jedi.__file__))))")
    # Run the doctests in this module
    tox -e py test/test_evaluate/test_docstring.py

"""

from textwrap import dedent
import jedi
from ..helpers import unittest

try:
    import numpydoc  # NOQA
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

    # ---- Numpy Style Tests ---

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

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpy_returns(self):
        s = dedent('''
        def foobar(x, y):
            """
            Returns
            ----------
            int
            """
            return x + y

        def bazbiz():
            z = foobar(2, 2)
            z.''')
        script = jedi.Script(s)
        names = [c.name for c in script.completions()]
        assert 'numerator' in names

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpy_follow_args(self):
        from jedi.evaluate import docstrings
        from jedi._compatibility import builtins
        numpy_source = dedent('''
        def foobar(x, y):
            """
            Parameters
            ----------
            x : int or str or list
            y : {'foo', 'bar', 100500}, optional
            """
            ''')
        script = jedi.Script(numpy_source)
        func = script._get_module().names_dict['foobar'][0].parent
        evaluator = script._evaluator
        x_param = func.names_dict['x'][0].parent
        y_param = func.names_dict['y'][0].parent
        x_type_list = docstrings.follow_param(evaluator, x_param)
        y_type_list = docstrings.follow_param(evaluator, y_param)
        assert len(x_type_list) == 3
        assert len(y_type_list) == 2
        y_base_objs = set([t.base.obj for t in y_type_list])
        x_base_objs = set([t.base.obj for t in x_type_list])
        assert x_base_objs == {builtins.int, builtins.str, builtins.list}
        assert y_base_objs == {builtins.int, builtins.str}

    @unittest.skipIf(numpydoc_unavailable, 'numpydoc module is unavailable')
    def test_numpy_find_return_types(self):
        from jedi.evaluate import docstrings
        from jedi._compatibility import builtins
        s = dedent('''
        def foobar(x, y):
            """
            Returns
            ----------
            int
            """
            return x + y
            ''')
        script = jedi.Script(s)
        func = script._get_module().names_dict['foobar'][0].parent
        evaluator = script._evaluator
        types = docstrings.find_return_types(evaluator, func)
        assert len(types) == 1
        assert types[0].base.obj is builtins.int

    # ---- Google Style Tests ---

    def test_googlestyle_docstring(self):
        s = dedent('''
        def foobar(x, y):
            """
            Args:
                x (int):
                y (str):
            """
            y.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names

    def test_googledoc_docstring_set_of_values(self):
        s = dedent('''
        def foobar(x, y):
            """
            Args:
                x ({'foo', 'bar', 100500}):
            """
            x.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names
        assert 'numerator' in names

    def test_googledoc_alternative_types(self):
        s = dedent('''
        def foobar(x, y):
            """
            Args:
                x (int or str or list):
            """
            x.''')
        names = [c.name for c in jedi.Script(s).completions()]
        assert 'isupper' in names
        assert 'capitalize' in names
        assert 'numerator' in names
        assert 'append' in names

    def test_google_returns(self):
        s = dedent('''
        def foobar(x, y):
            """
            Returns:
                int: sum of x and y
            """
            return x + y

        def bazbiz():
            z = foobar(2, 2)
            z.''')
        script = jedi.Script(s)
        names = [c.name for c in script.completions()]
        assert 'numerator' in names

    def test_google_follow_args(self):
        from jedi.evaluate import docstrings
        from jedi._compatibility import builtins
        google_source = dedent('''
        def foobar(x, y):
            """
            Args:
                x (int or str or list):
                y ({'foo', 'bar', 100500}):
            """
            ''')
        script = jedi.Script(google_source)
        func = script._get_module().names_dict['foobar'][0].parent
        evaluator = script._evaluator
        x_param = func.names_dict['x'][0].parent
        y_param = func.names_dict['y'][0].parent
        x_type_list = docstrings.follow_param(evaluator, x_param)
        y_type_list = docstrings.follow_param(evaluator, y_param)
        assert len(x_type_list) == 3
        assert len(y_type_list) == 2
        y_base_objs = set([t.base.obj for t in y_type_list])
        x_base_objs = set([t.base.obj for t in x_type_list])
        assert x_base_objs == {builtins.int, builtins.str, builtins.list}
        assert y_base_objs == {builtins.int, builtins.str}

    def test_google_find_return_types(self):
        from jedi.evaluate import docstrings
        from jedi._compatibility import builtins
        s = dedent('''
        def foobar(x, y):
            """
            Returns:
                int: sum of x and y
            """
            return x + y
            ''')
        script = jedi.Script(s)
        func = script._get_module().names_dict['foobar'][0].parent
        evaluator = script._evaluator
        types = docstrings.find_return_types(evaluator, func)
        assert len(types) == 1
        assert types[0].base.obj is builtins.int
