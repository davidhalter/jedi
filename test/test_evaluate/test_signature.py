import pytest

from jedi.evaluate.gradual.conversion import stub_to_actual_context_set


def test_compiled_signature(Script):
    code = 'import math; math.cos'
    sig = 'cos(x, /)'
    d, = Script(code).goto_definitions()
    context, = d._name.infer()
    compiled, = stub_to_actual_context_set(context)
    signature, = compiled.get_signatures()
    assert signature.to_string() == sig
    assert signature.get_param_names() == []
    assert signature.annotation is None
