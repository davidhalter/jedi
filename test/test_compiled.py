from jedi._compatibility import builtins
from jedi.evaluate import compiled
from jedi.evaluate import Evaluator


def test_simple():
    e = Evaluator()
    bltn = compiled.PyObject(builtins)
    obj = compiled.PyObject('_str_', bltn)
    upper = e.find_types(obj, 'upper')
    assert len(upper) == 1
    objs = e.execute(upper[0])
    assert len(objs) == 1
    assert isinstance(objs[0].obj, str)
