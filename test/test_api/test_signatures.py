import pytest

_tuple_code = 'from typing import Tuple\ndef f(x: Tuple[int]): ...\nf'


@pytest.mark.parametrize(
    'code, expected_params, execute_annotation', [
        ('def f(x: 1, y): ...\nf', [None, None], True),
        ('def f(x: 1, y): ...\nf', ['instance int', None], False),
        ('def f(x: int): ...\nf', ['instance int'], True),
        ('from typing import List\ndef f(x: List[int]): ...\nf', ['instance list'], True),
        ('from typing import List\ndef f(x: List[int]): ...\nf', ['class list'], False),
        (_tuple_code, ['Tuple: _SpecialForm = ...'], True),
        (_tuple_code, ['Tuple: _SpecialForm = ...'], False),
        ('x=str\ndef f(p: x): ...\nx=int\nf', ['instance int'], True),
    ]
)
def test_param_annotation(Script, code, expected_params, execute_annotation):
    func, = Script(code).goto_assignments()
    sig, = func.get_signatures()
    for p, expected in zip(sig.params, expected_params):
        annotations = p.infer_annotation(execute_annotation=execute_annotation)
        if expected is None:
            assert not annotations
        else:
            annotation, = annotations
            assert annotation.description == expected


@pytest.mark.parametrize(
    'code, expected_params', [
        ('def f(x=1, y=int, z): ...\nf', ['instance int', 'class int', None]),
        ('def f(*args, **kwargs): ...\nf', [None, None]),
        ('x=1\ndef f(p=x): ...\nx=""\nf', ['instance int']),
    ]
)
def test_param_default(Script, code, expected_params):
    func, = Script(code).goto_assignments()
    sig, = func.get_signatures()
    for p, expected in zip(sig.params, expected_params):
        annotations = p.infer_default()
        if expected is None:
            assert not annotations
        else:
            annotation, = annotations
            assert annotation.description == expected
