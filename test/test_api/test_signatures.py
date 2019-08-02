import pytest


@pytest.mark.parametrize(
    'code, expected_params', [
        ('def f(x: 1, y): ...\nf', [None, None]),
        ('def f(x: int): ...\nf', ['instance int']),
        ('from typing import List\ndef f(x: List[int]): ...\nf', ['instance list']),
        ('from typing import Tuple\ndef f(x: Tuple[int]): ...\nf', ['Tuple: _SpecialForm = ...']),
        ('x=str\ndef f(p: x): ...\nx=int\nf', ['instance int']),
    ]
)
def test_param_annotation(Script, code, expected_params):
    func, = Script(code).goto_assignments()
    sig, = func.get_signatures()
    for p, expected in zip(sig.params, expected_params):
        if expected is None:
            assert not p.infer_annotation()
        else:
            annotation, = p.infer_annotation()
            assert annotation.description == expected
