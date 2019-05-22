import pytest
from operator import ge, lt

from jedi.evaluate.gradual.conversion import stub_to_actual_context_set


@pytest.mark.parametrize(
    'code, sig, names, op, version', [
        ('import math; math.cos', 'cos(x)', ['x'], lt, (3, 7)),
        ('import math; math.cos', 'cos(x, /)', ['x'], ge, (3, 7)),

        ('next', 'next(iterator, default=None)', ['iterator', 'default'], ge, (2, 7)),

        ('pow', 'pow(x, y, z=None) -> number', ['x', 'y', 'z'], lt, (3, 5)),
        ('pow', 'pow(x, y, z=None, /)', ['x', 'y', 'z'], ge, (3, 5)),

        ('bytes.partition', 'partition(self, sep) -> (head, sep, tail)', ['self', 'sep'], lt, (3, 5)),
        ('bytes.partition', 'partition(self, sep, /)', ['self', 'sep'], ge, (3, 5)),

        ('bytes().partition', 'partition(sep) -> (head, sep, tail)', ['sep'], lt, (3, 5)),
        ('bytes().partition', 'partition(sep, /)', ['sep'], ge, (3, 5)),
    ]
)
def test_compiled_signature(Script, environment, code, sig, names, op, version):
    if not op(environment.version_info, version):
        return  # The test right next to it should take over.

    d, = Script(code).goto_definitions()
    context, = d._name.infer()
    compiled, = stub_to_actual_context_set(context)
    signature, = compiled.get_signatures()
    assert signature.to_string() == sig
    assert [n.string_name for n in signature.get_param_names()] == names
    assert signature.annotation is None
