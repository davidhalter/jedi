from textwrap import dedent
import inspect
import warnings

import pytest

from ..helpers import TestCase
from jedi import cache
from jedi._compatibility import is_py33


def assert_signature(Script, source, expected_name, expected_index=0, line=None, column=None):
    signatures = Script(source, line, column).call_signatures()

    assert len(signatures) <= 1

    if not signatures:
        assert expected_name is None, \
            'There are no signatures, but `%s` expected.' % expected_name
    else:
        assert signatures[0].name == expected_name
        assert signatures[0].index == expected_index
        return signatures[0]


def test_valid_call(Script):
    assert_signature(Script, 'str()', 'str', column=4)


class TestCallSignatures(TestCase):
    @pytest.fixture(autouse=True)
    def init(self, Script):
        self.Script = Script

    def _run_simple(self, source, name, index=0, column=None, line=1):
        assert_signature(self.Script, source, name, index, line, column)

    def test_simple(self):
        run = self._run_simple

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

    def test_more_complicated(self):
        run = self._run_simple

        s4 = 'abs(zip(), , set,'
        run(s4, None, column=3)
        run(s4, 'abs', 0, 4)
        run(s4, 'zip', 0, 8)
        run(s4, 'abs', 0, 9)
        run(s4, 'abs', None, 10)

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

    def test_issue_57(self):
        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        self._run_simple(s, 'func', 0, column=13, line=2)

    def test_flows(self):
        # jedi-vim #9
        self._run_simple("with open(", 'open', 0)

        # jedi-vim #11
        self._run_simple("for sorted(", 'sorted', 0)
        self._run_simple("for s in sorted(", 'sorted', 0)


def test_call_signatures_empty_parentheses_pre_space(Script):
    s = dedent("""\
    def f(a, b):
        pass
    f( )""")
    assert_signature(Script, s, 'f', 0, line=3, column=3)


def test_multiple_signatures(Script):
    s = dedent("""\
    if x:
        def f(a, b):
            pass
    else:
        def f(a, b):
            pass
    f(""")
    assert len(Script(s).call_signatures()) == 2


def test_call_signatures_whitespace(Script):
    s = dedent("""\
    abs( 
    def x():
        pass
    """)
    assert_signature(Script, s, 'abs', 0, line=1, column=5)


def test_decorator_in_class(Script):
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
    assert x == ['param *args']


def test_additional_brackets(Script):
    assert_signature(Script, 'str((', 'str', 0)


def test_unterminated_strings(Script):
    assert_signature(Script, 'str(";', 'str', 0)


def test_whitespace_before_bracket(Script):
    assert_signature(Script, 'str (', 'str', 0)
    assert_signature(Script, 'str (";', 'str', 0)
    assert_signature(Script, 'str\n(', None)


def test_brackets_in_string_literals(Script):
    assert_signature(Script, 'str (" (', 'str', 0)
    assert_signature(Script, 'str (" )', 'str', 0)


def test_function_definitions_should_break(Script):
    """
    Function definitions (and other tokens that cannot exist within call
    signatures) should break and not be able to return a call signature.
    """
    assert_signature(Script, 'str(\ndef x', 'str', 0)
    assert not Script('str(\ndef x(): pass').call_signatures()


def test_flow_call(Script):
    assert not Script('if (1').call_signatures()


def test_chained_calls(Script):
    source = dedent('''
    class B():
      def test2(self, arg):
        pass

    class A():
      def test1(self):
        return B()

    A().test1().test2(''')

    assert_signature(Script, source, 'test2', 0)


def test_return(Script):
    source = dedent('''
    def foo():
        return '.'.join()''')

    assert_signature(Script, source, 'join', 0, column=len("    return '.'.join("))


def test_call_signature_on_module(Script):
    """github issue #240"""
    s = 'import datetime; datetime('
    # just don't throw an exception (if numpy doesn't exist, just ignore it)
    assert Script(s).call_signatures() == []


def test_complex(Script):
    s = """
            def abc(a,b):
                pass

            def a(self):
                abc(

            if 1:
                pass
        """
    assert_signature(Script, s, 'abc', 0, line=6, column=20)
    s = """
            import re
            def huhu(it):
                re.compile(
                return it * 2
        """
    assert_signature(Script, s, 'compile', 0, line=4, column=27)

    # jedi-vim #70
    s = """def foo("""
    assert Script(s).call_signatures() == []

    # jedi-vim #116
    s = """import itertools; test = getattr(itertools, 'chain'); test("""
    assert_signature(Script, s, 'chain', 0)


def _params(Script, source, line=None, column=None):
    signatures = Script(source, line, column).call_signatures()
    assert len(signatures) == 1
    return signatures[0].params


def test_param_name(Script):
    if not is_py33:
        p = _params(Script, '''int(''')
        # int is defined as: `int(x[, base])`
        assert p[0].name == 'x'
        # `int` docstring has been redefined:
        # http://bugs.python.org/issue14783
        # TODO have multiple call signatures for int (like in the docstr)
        #assert p[1].name == 'base'

    p = _params(Script, '''open(something,''')
    assert p[0].name in ['file', 'name']
    assert p[1].name == 'mode'


def test_builtins(Script):
    """
    The self keyword should be visible even for builtins, if not
    instantiated.
    """
    p = _params(Script, 'str.endswith(')
    assert p[0].name == 'self'
    assert p[1].name == 'suffix'
    p = _params(Script, 'str().endswith(')
    assert p[0].name == 'suffix'


def test_signature_is_definition(Script):
    """
    Through inheritance, a call signature is a sub class of Definition.
    Check if the attributes match.
    """
    s = """class Spam(): pass\nSpam"""
    signature = Script(s + '(').call_signatures()[0]
    definition = Script(s + '(', column=0).goto_definitions()[0]
    signature.line == 1
    signature.column == 6

    # Now compare all the attributes that a CallSignature must also have.
    for attr_name in dir(definition):
        dont_scan = ['defined_names', 'parent', 'goto_assignments', 'params']
        if attr_name.startswith('_') or attr_name in dont_scan:
            continue

        # Might trigger some deprecation warnings.
        with warnings.catch_warnings(record=True):
            attribute = getattr(definition, attr_name)
            signature_attribute = getattr(signature, attr_name)
            if inspect.ismethod(attribute):
                assert attribute() == signature_attribute()
            else:
                assert attribute == signature_attribute


def test_no_signature(Script):
    # str doesn't have a __call__ method
    assert Script('str()(').call_signatures() == []

    s = dedent("""\
    class X():
        pass
    X()(""")
    assert Script(s).call_signatures() == []
    assert len(Script(s, column=2).call_signatures()) == 1
    assert Script('').call_signatures() == []


def test_dict_literal_in_incomplete_call(Script):
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


def test_completion_interference(Script):
    """Seems to cause problems, see also #396."""
    cache.parser_cache.pop(None, None)
    assert Script('open(').call_signatures()

    # complete something usual, before doing the same call_signatures again.
    assert Script('from datetime import ').completions()

    assert Script('open(').call_signatures()


def test_keyword_argument_index(Script, environment):
    def get(source, column=None):
        return Script(source, column=column).call_signatures()[0]

    # The signature of sorted changed from 2 to 3.
    py2_offset = int(environment.version_info.major == 2)
    assert get('sorted([], key=a').index == 1 + py2_offset
    assert get('sorted([], key=').index == 1 + py2_offset
    assert get('sorted([], no_key=a').index is None

    kw_func = 'def foo(a, b): pass\nfoo(b=3, a=4)'
    assert get(kw_func, column=len('foo(b')).index == 0
    assert get(kw_func, column=len('foo(b=')).index == 1
    assert get(kw_func, column=len('foo(b=3, a=')).index == 0

    kw_func_simple = 'def foo(a, b): pass\nfoo(b=4)'
    assert get(kw_func_simple, column=len('foo(b')).index == 0
    assert get(kw_func_simple, column=len('foo(b=')).index == 1

    args_func = 'def foo(*kwargs): pass\n'
    assert get(args_func + 'foo(a').index == 0
    assert get(args_func + 'foo(a, b').index == 0

    kwargs_func = 'def foo(**kwargs): pass\n'
    assert get(kwargs_func + 'foo(a=2').index == 0
    assert get(kwargs_func + 'foo(a=2, b=2').index == 0

    both = 'def foo(*args, **kwargs): pass\n'
    assert get(both + 'foo(a=2').index == 1
    assert get(both + 'foo(a=2, b=2').index == 1
    assert get(both + 'foo(a=2, b=2)', column=len('foo(b=2, a=2')).index == 1
    assert get(both + 'foo(a, b, c').index == 0


def test_bracket_start(Script):
    def bracket_start(src):
        signatures = Script(src).call_signatures()
        assert len(signatures) == 1
        return signatures[0].bracket_start

    assert bracket_start('str(') == (1, 3)


def test_different_caller(Script):
    """
    It's possible to not use names, but another function result or an array
    index and then get the call signature of it.
    """

    assert_signature(Script, '[str][0](', 'str', 0)
    assert_signature(Script, '[str][0]()', 'str', 0, column=len('[str][0]('))

    assert_signature(Script, '(str)(', 'str', 0)
    assert_signature(Script, '(str)()', 'str', 0, column=len('(str)('))


def test_in_function(Script):
    code = dedent('''\
    class X():
        @property
        def func(''')
    assert not Script(code).call_signatures()


def test_lambda_params(Script):
    code = dedent('''\
    my_lambda = lambda x: x+1
    my_lambda(1)''')
    sig, = Script(code, column=11).call_signatures()
    assert sig.index == 0
    assert sig.name == '<lambda>'
    assert [p.name for p in sig.params] == ['x']


def test_class_creation(Script):
    code = dedent('''\
    class X():
        def __init__(self, foo, bar):
            self.foo = foo
    ''')
    sig, = Script(code + 'X(').call_signatures()
    assert sig.index == 0
    assert sig.name == 'X'
    assert [p.name for p in sig.params] == ['foo', 'bar']

    sig, = Script(code + 'X.__init__(').call_signatures()
    assert [p.name for p in sig.params] == ['self', 'foo', 'bar']
    sig, = Script(code + 'X().__init__(').call_signatures()
    assert [p.name for p in sig.params] == ['foo', 'bar']


def test_call_magic_method(Script):
    code = dedent('''\
    class X():
        def __call__(self, baz):
            pass
    ''')
    sig, = Script(code + 'X()(').call_signatures()
    assert sig.index == 0
    assert sig.name == 'X'
    assert [p.name for p in sig.params] == ['baz']

    sig, = Script(code + 'X.__call__(').call_signatures()
    assert [p.name for p in sig.params] == ['self', 'baz']
    sig, = Script(code + 'X().__call__(').call_signatures()
    assert [p.name for p in sig.params] == ['baz']
