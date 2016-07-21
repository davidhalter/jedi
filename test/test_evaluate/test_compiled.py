from jedi._compatibility import builtins, is_py3
from jedi.parser import load_grammar
from jedi.parser.tree import Function
from jedi.evaluate import compiled, representation
from jedi.evaluate import Evaluator
from jedi import Script


def _evaluator():
    return Evaluator(load_grammar())


def test_simple():
    e = _evaluator()
    bltn = compiled.CompiledObject(e, builtins)
    obj = compiled.CompiledObject(e, '_str_', bltn)
    upper = e.find_types(obj, 'upper')
    assert len(upper) == 1
    objs = list(e.execute(list(upper)[0]))
    assert len(objs) == 1
    assert isinstance(objs[0], representation.Instance)


def test_fake_loading():
    e = _evaluator()
    assert isinstance(compiled.create(e, next), Function)

    builtin = compiled.get_special_object(e, 'BUILTINS')
    string = builtin.get_subscope_by_name('str')
    from_name = compiled._create_from_name(e, builtin, string, '__init__')
    assert isinstance(from_name, Function)


def test_fake_docstr():
    assert compiled.create(_evaluator(), next).raw_doc == next.__doc__


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
