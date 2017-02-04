from textwrap import dedent

from jedi._compatibility import builtins, is_py3
from jedi.parser import load_grammar
from jedi.evaluate import compiled, instance
from jedi.evaluate.representation import FunctionContext
from jedi.evaluate import Evaluator
from jedi import Script


def _evaluator():
    return Evaluator(load_grammar())


def test_simple():
    e = _evaluator()
    bltn = compiled.CompiledObject(e, builtins)
    obj = compiled.CompiledObject(e, '_str_', bltn)
    upper, = obj.py__getattribute__('upper')
    objs = list(upper.execute_evaluated())
    assert len(objs) == 1
    assert isinstance(objs[0], instance.CompiledInstance)


def test_fake_loading():
    e = _evaluator()
    assert isinstance(compiled.create(e, next), FunctionContext)

    builtin = compiled.get_special_object(e, 'BUILTINS')
    string, = builtin.py__getattribute__('str')
    from_name = compiled._create_from_name(e, builtin, string, '__init__')
    assert isinstance(from_name, FunctionContext)


def test_fake_docstr():
    assert compiled.create(_evaluator(), next).tree_node.raw_doc == next.__doc__


def test_parse_function_doc_illegal_docstr():
    docstr = """
    test_func(o

    doesn't have a closing bracket.
    """
    assert ('', '') == compiled._parse_function_doc(docstr)


def test_doc():
    """
    Even CompiledObject docs always return empty docstrings - not None, that's
    just a Jedi API definition.
    """
    obj = compiled.CompiledObject(_evaluator(), ''.__getnewargs__)
    assert obj.doc == ''


def test_string_literals():
    def typ(string):
        d = Script("a = %s; a" % string).goto_definitions()[0]
        return d.name

    assert typ('""') == 'str'
    assert typ('r""') == 'str'
    if is_py3:
        assert typ('br""') == 'bytes'
        assert typ('b""') == 'bytes'
        assert typ('u""') == 'str'
    else:
        assert typ('b""') == 'str'
        assert typ('u""') == 'unicode'


def test_method_completion():
    code = dedent('''
    class Foo:
        def bar(self):
            pass

    foo = Foo()
    foo.bar.__func__''')
    if is_py3:
        result = []
    else:
        result = ['__func__']
    assert [c.name for c in Script(code).completions()] == result


def test_decorator_global():
    code = dedent('''
    import abc
    @abc''')
    result = ['abc']
    assert [c.name for c in Script(code).completions()] == result


def test_decorator_dotted():
    code = dedent('''
    import abc
    @abc.abstractmethod''')
    result = ['abstractmethod']
    assert [c.name for c in Script(code).completions()] == result
