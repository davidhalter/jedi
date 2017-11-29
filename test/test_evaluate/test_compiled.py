from textwrap import dedent

import parso

from jedi._compatibility import builtins, is_py3
from jedi.evaluate import compiled
from jedi.evaluate.context import instance
from jedi.evaluate.context.function import FunctionContext
from jedi.evaluate import Evaluator
from jedi.evaluate.project import Project
from jedi.parser_utils import clean_scope_docstring
from jedi import Script


def test_simple(evaluator):
    obj = compiled.create(evaluator, '_str_')
    upper, = obj.py__getattribute__('upper')
    objs = list(upper.execute_evaluated())
    assert len(objs) == 1
    assert isinstance(objs[0], instance.CompiledInstance)


def test_fake_loading(evaluator):
    builtin = compiled.get_special_object(evaluator, 'BUILTINS')
    string, = builtin.py__getattribute__('str')
    from_name = compiled.context._create_from_name(evaluator, string, '__init__')
    assert from_name.tree_node


def test_fake_docstr(evaluator):
    next_ = compiled.create(evaluator, next)
    assert next_.py__doc__()
    assert next_.tree_node is not None
    assert next_.py__doc__() == next.__doc__


def test_parse_function_doc_illegal_docstr():
    docstr = """
    test_func(o

    doesn't have a closing bracket.
    """
    assert ('', '') == compiled.context._parse_function_doc(docstr)


def test_doc(evaluator):
    """
    Even CompiledObject docs always return empty docstrings - not None, that's
    just a Jedi API definition.
    """
    obj = compiled.create(evaluator, ''.__getnewargs__)
    assert obj.py__doc__() == ''


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


def test_time_docstring():
    import time
    comp, = Script('import time\ntime.sleep').completions()
    assert comp.docstring() == time.sleep.__doc__


def test_dict_values():
    assert Script('import sys\nsys.modules["alshdb;lasdhf"]').goto_definitions()
