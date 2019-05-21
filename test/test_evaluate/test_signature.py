import pytest
from operator import ge, le

from jedi.evaluate.gradual.conversion import stub_to_actual_context_set


@pytest.mark.parametrize(
    'code, sig, names, op, version', [
        ('import math; math.cos', 'cos(x)', ['x'], le, (3, 6)),
        ('import math; math.cos', 'cos(x, /)', ['x'], ge, (3, 7)),

        ('next', 'next(iterator, default=None)', ['iterator', 'default'], ge, (2, 7)),
    ]
)
def test_compiled_signature(Script, environment, code, sig, names, op, version):
    if not op(environment.version_info, version):
        pytest.skip("Not running for this version")

    d, = Script(code).goto_definitions()
    context, = d._name.infer()
    compiled, = stub_to_actual_context_set(context)
    signature, = compiled.get_signatures()
    assert signature.to_string() == sig
    assert [n.string_name for n in signature.get_param_names()] == names
    assert signature.annotation is None
