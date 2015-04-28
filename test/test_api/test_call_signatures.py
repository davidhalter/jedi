from textwrap import dedent
import inspect

from ..helpers import TestCase
from jedi import Script
from jedi import cache
from jedi._compatibility import is_py33


class TestCallSignatures(TestCase):
    def _run(self, source, expected_name, expected_index=0, line=None, column=None):
        signatures = Script(source, line, column).call_signatures()

        assert len(signatures) <= 1

        if not signatures:
            assert expected_name is None
        else:
            assert signatures[0].name == expected_name
            assert signatures[0].index == expected_index

    def _run_simple(self, source, name, index=0, column=None, line=1):
        self._run(source, name, index, line, column)

    def test_valid_call(self):
        self._run('str()', 'str', column=4)

    def test_simple(self):
        run = self._run_simple
        s7 = "str().upper().center("
        s8 = "str(int[zip("
        run(s7, 'center', 0)

        # simple
        s1 = "sorted(a, str("
        run(s1, 'sorted', 0, 7)
        run(s1, 'sorted', 1, 9)
        run(s1, 'sorted', 1, 10)
        run(s1, 'sorted', 1, 11)
        run(s1, 'str', 0, 14)

        s2 = "abs(), "
        run(s2, 'abs', 0, 4)
        run(s2, None, column=5)
        run(s2, None)

        s3 = "abs()."
        run(s3, None, column=5)
        run(s3, None)

        # more complicated
        s4 = 'abs(zip(), , set,'
        run(s4, None, column=3)
        run(s4, 'abs', 0, 4)
        run(s4, 'zip', 0, 8)
        run(s4, 'abs', 0, 9)
        #run(s4, 'abs', 1, 10)

        s5 = "sorted(1,\nif 2:\n def a():"
        run(s5, 'sorted', 0, 7)
        run(s5, 'sorted', 1, 9)

        s6 = "str().center("
        run(s6, 'center', 0)
        run(s6, 'str', 0, 4)

        s7 = "str().upper().center("
        s8 = "str(int[zip("
        run(s7, 'center', 0)
        run(s8, 'zip', 0)
        run(s8, 'str', 0, 8)

        run("import time; abc = time; abc.sleep(", 'sleep', 0)

        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        run(s, 'func', 0, column=13, line=2)

    def test_flows(self):
        # jedi-vim #9
        self._run_simple("with open(", 'open', 0)

        # jedi-vim #11
        self._run_simple("for sorted(", 'sorted', 0)
        self._run_simple("for s in sorted(", 'sorted', 0)

    def test_complex(self):
        s = """
                def abc(a,b):
                    pass

                def a(self):
                    abc(

                if 1:
                    pass
            """
        self._run(s, 'abc', 0, line=6, column=24)
        s = """
                import re
                def huhu(it):
                    re.compile(
                    return it * 2
            """
        self._run(s, 'compile', 0, line=4, column=31)

        # jedi-vim #70
        s = """def foo("""
        assert Script(s).call_signatures() == []

        # jedi-vim #116
        s = """import itertools; test = getattr(itertools, 'chain'); test("""
        self._run(s, 'chain', 0)

    def test_call_signature_on_module(self):
        """github issue #240"""
        s = 'import datetime; datetime('
        # just don't throw an exception (if numpy doesn't exist, just ignore it)
        assert Script(s).call_signatures() == []

    def test_call_signatures_empty_parentheses_pre_space(self):
        s = dedent("""\
        def f(a, b):
            pass
        f( )""")
        self._run(s, 'f', 0, line=3, column=3)

    def test_multiple_signatures(self):
        s = dedent("""\
        if x:
            def f(a, b):
                pass
        else:
            def f(a, b):
                pass
        f(""")
        assert len(Script(s).call_signatures()) == 2

    def test_call_signatures_whitespace(self):
        s = dedent("""\
        abs( 
        def x():
            pass
        """)
        self._run(s, 'abs', 0, line=1, column=5)

    def test_decorator_in_class(self):
        """
        There's still an implicit param, with a decorator.
        Github issue #319.
        """
        s = dedent("""\
        def static(func):
            def wrapped(obj, *args):
                return f(type(obj), *args)
            return wrapped

        class C(object):
            @static
            def test(cls):
                return 10

        C().test(""")

        signatures = Script(s).call_signatures()
        assert len(signatures) == 1
        x = [p.description for p in signatures[0].params]
        assert x == ['*args']

    def test_additional_brackets(self):
        self._run('str((', 'str', 0)

    def test_unterminated_strings(self):
        self._run('str(";', 'str', 0)

    def test_whitespace_before_bracket(self):
        self._run('str (', 'str', 0)
        self._run('str (";', 'str', 0)
        # TODO this is not actually valid Python, the newline token should be
        # ignored.
        self._run('str\n(', 'str', 0)

    def test_brackets_in_string_literals(self):
        self._run('str (" (', 'str', 0)
        self._run('str (" )', 'str', 0)

    def test_function_definitions_should_break(self):
        """
        Function definitions (and other tokens that cannot exist within call
        signatures) should break and not be able to return a call signature.
        """
        assert not Script('str(\ndef x').call_signatures()

    def test_flow_call(self):
        assert not Script('if (1').call_signatures()

    def test_chained_calls(self):
        source = dedent('''
        class B():
          def test2(self, arg):
            pass

        class A():
          def test1(self):
            return B()

        A().test1().test2(''')

        self._run(source, 'test2', 0)

    def test_return(self):
        source = dedent('''
        def foo():
            return '.'.join()''')

        self._run(source, 'join', 0, column=len("    return '.'.join("))


class TestParams(TestCase):
    def params(self, source, line=None, column=None):
        signatures = Script(source, line, column).call_signatures()
        assert len(signatures) == 1
        return signatures[0].params

    def test_param_name(self):
        if not is_py33:
            p = self.params('''int(''')
            # int is defined as: `int(x[, base])`
            assert p[0].name == 'x'
            # `int` docstring has been redefined:
            # http://bugs.python.org/issue14783
            # TODO have multiple call signatures for int (like in the docstr)
            #assert p[1].name == 'base'

        p = self.params('''open(something,''')
        assert p[0].name in ['file', 'name']
        assert p[1].name == 'mode'

    def test_builtins(self):
        """
        The self keyword should be visible even for builtins, if not
        instantiated.
        """
        p = self.params('str.endswith(')
        assert p[0].name == 'self'
        assert p[1].name == 'suffix'
        p = self.params('str().endswith(')
        assert p[0].name == 'suffix'



def test_signature_is_definition():
    """
    Through inheritance, a call signature is a sub class of Definition.
    Check if the attributes match.
    """
    s = """class Spam(): pass\nSpam"""
    signature = Script(s + '(').call_signatures()[0]
    definition = Script(s + '(').goto_definitions()[0]
    signature.line == 1
    signature.column == 6

    # Now compare all the attributes that a CallSignature must also have.
    for attr_name in dir(definition):
        dont_scan = ['defined_names', 'line_nr', 'start_pos', 'documentation',
                     'doc', 'parent', 'goto_assignments']
        if attr_name.startswith('_') or attr_name in dont_scan:
            continue
        attribute = getattr(definition, attr_name)
        signature_attribute = getattr(signature, attr_name)
        if inspect.ismethod(attribute):
            assert attribute() == signature_attribute()
        else:
            assert attribute == signature_attribute


def test_no_signature():
    # str doesn't have a __call__ method
    assert Script('str()(').call_signatures() == []

    s = dedent("""\
    class X():
        pass
    X()(""")
    assert Script(s).call_signatures() == []
    assert len(Script(s, column=2).call_signatures()) == 1


def test_dict_literal_in_incomplete_call():
    source = """\
    import json

    def foo():
        json.loads(

        json.load.return_value = {'foo': [],
                                  'bar': True}

        c = Foo()
    """

    script = Script(dedent(source), line=4, column=15)
    assert script.call_signatures()


def test_completion_interference():
    """Seems to cause problems, see also #396."""
    cache.parser_cache.pop(None, None)
    assert Script('open(').call_signatures()

    # complete something usual, before doing the same call_signatures again.
    assert Script('from datetime import ').completions()

    assert Script('open(').call_signatures()


def test_signature_index():
    def get(source):
        return Script(source).call_signatures()[0]

    assert get('sorted([], key=a').index == 2
    assert get('sorted([], no_key=a').index is None

    args_func = 'def foo(*kwargs): pass\n'
    assert get(args_func + 'foo(a').index == 0
    assert get(args_func + 'foo(a, b').index == 0

    kwargs_func = 'def foo(**kwargs): pass\n'
    assert get(kwargs_func + 'foo(a=2').index == 0
    assert get(kwargs_func + 'foo(a=2, b=2').index == 0

    both = 'def foo(*args, **kwargs): pass\n'
    assert get(both + 'foo(a=2').index == 1
    assert get(both + 'foo(a=2, b=2').index == 1
    assert get(both + 'foo(a, b, c').index == 0


def test_bracket_start():
    def bracket_start(src):
        signatures = Script(src).call_signatures()
        assert len(signatures) == 1
        return signatures[0].bracket_start

    assert bracket_start('str(') == (1, 3)
