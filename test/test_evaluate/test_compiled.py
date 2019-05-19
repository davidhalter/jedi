from textwrap import dedent

import pytest

from jedi.evaluate import compiled
from jedi.evaluate.helpers import execute_evaluated
from jedi.evaluate.gradual.conversion import stub_to_actual_context_set


def test_simple(evaluator, environment):
    obj = compiled.create_simple_object(evaluator, u'_str_')
    upper, = obj.py__getattribute__(u'upper')
    objs = list(execute_evaluated(upper))
    assert len(objs) == 1
    if environment.version_info.major == 2:
        expected = 'unicode'
    else:
        expected = 'str'
    assert objs[0].name.string_name == expected


def test_builtin_loading(evaluator):
    string, = evaluator.builtins_module.py__getattribute__(u'str')
    from_name, = string.py__getattribute__(u'__init__')
    assert from_name.tree_node
    assert not from_name.py__doc__()  # It's a stub


def test_next_docstr(evaluator):
    next_ = compiled.builtin_from_name(evaluator, u'next')
    assert next_.tree_node is not None
    assert next_.py__doc__() == ''  # It's a stub
    for non_stub in stub_to_actual_context_set(next_):
        assert non_stub.py__doc__() == next.__doc__


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
    str_ = compiled.create_simple_object(evaluator, u'')
    # Equals `''.__getnewargs__`
    obj, = str_.py__getattribute__(u'__getnewargs__')
    assert obj.py__doc__() == ''


def test_string_literals(Script, environment):
    def typ(string):
        d = Script("a = %s; a" % string).goto_definitions()[0]
        return d.name

    assert typ('""') == 'str'
    assert typ('r""') == 'str'
    if environment.version_info.major > 2:
        assert typ('br""') == 'bytes'
        assert typ('b""') == 'bytes'
        assert typ('u""') == 'str'
    else:
        assert typ('b""') == 'str'
        assert typ('u""') == 'unicode'


def test_method_completion(Script, environment):
    code = dedent('''
    class Foo:
        def bar(self):
            pass

    foo = Foo()
    foo.bar.__func__''')
    assert [c.name for c in Script(code).completions()] == ['__func__']


def test_time_docstring(Script):
    import time
    comp, = Script('import time\ntime.sleep').completions()
    assert comp.docstring(raw=True) == time.sleep.__doc__
    expected = 'sleep(secs: float) -> None\n\n' + time.sleep.__doc__
    assert comp.docstring() == expected


def test_dict_values(Script, environment):
    if environment.version_info.major == 2:
        # It looks like typeshed for Python 2 returns Any.
        pytest.skip()
    assert Script('import sys\nsys.modules["alshdb;lasdhf"]').goto_definitions()


def test_getitem_on_none(Script):
    script = Script('None[1j]')
    assert not script.goto_definitions()
    issue, = script._evaluator.analysis
    assert issue.name == 'type-error-not-subscriptable'
