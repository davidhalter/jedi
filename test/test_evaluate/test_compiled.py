from jedi._compatibility import builtins
from jedi.parser.representation import Function
from jedi.evaluate import compiled
from jedi.evaluate import Evaluator


def test_simple():
    e = Evaluator()
    bltn = compiled.CompiledObject(builtins)
    obj = compiled.CompiledObject('_str_', bltn)
    upper = e.find_types(obj, 'upper')
    assert len(upper) == 1
    objs = list(e.execute(upper[0]))
    assert len(objs) == 1
    assert objs[0].obj is str


def test_fake_loading():
    assert isinstance(compiled.create(Evaluator(), next), Function)

    string = compiled.builtin.get_subscope_by_name('str')
    from_name = compiled._create_from_name(
        compiled.builtin,
        string,
        '__init__'
    )
    assert isinstance(from_name, Function)


def test_fake_docstr():
    assert compiled.create(Evaluator(), next).raw_doc == next.__doc__


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
    obj = compiled.CompiledObject(''.__getnewargs__)
    assert obj.doc == ''
