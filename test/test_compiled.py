from jedi._compatibility import builtins
from jedi.evaluate import compiled
from jedi.evaluate import Evaluator


def test_simple():
    bltn = compiled.PyObject(builtins)
    obj = compiled.PyObject('_str_', bltn)
    upper = Evaluator().find_types(obj, 'upper')
    assert len(upper) == 1
