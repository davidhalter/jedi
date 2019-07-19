from textwrap import dedent
from operator import ge, lt

import pytest

from jedi.evaluate.gradual.conversion import _stub_to_python_context_set


@pytest.mark.parametrize(
    'code, sig, names, op, version', [
        ('import math; math.cos', 'cos(x, /)', ['x'], ge, (2, 7)),

        ('next', 'next(iterator, default=None, /)', ['iterator', 'default'], ge, (2, 7)),

        ('str', "str(object='', /) -> str", ['object'], ge, (2, 7)),

        ('pow', 'pow(x, y, z=None, /) -> number', ['x', 'y', 'z'], lt, (3, 5)),
        ('pow', 'pow(x, y, z=None, /)', ['x', 'y', 'z'], ge, (3, 5)),

        ('bytes.partition', 'partition(self, sep, /) -> (head, sep, tail)', ['self', 'sep'], lt, (3, 5)),
        ('bytes.partition', 'partition(self, sep, /)', ['self', 'sep'], ge, (3, 5)),

        ('bytes().partition', 'partition(sep, /) -> (head, sep, tail)', ['sep'], lt, (3, 5)),
        ('bytes().partition', 'partition(sep, /)', ['sep'], ge, (3, 5)),
    ]
)
def test_compiled_signature(Script, environment, code, sig, names, op, version):
    if not op(environment.version_info, version):
        return  # The test right next to it should take over.

    d, = Script(code).goto_definitions()
    context, = d._name.infer()
    compiled, = _stub_to_python_context_set(context)
    signature, = compiled.get_signatures()
    assert signature.to_string() == sig
    assert [n.string_name for n in signature.get_param_names()] == names


@pytest.mark.parametrize(
    'code, expected', [
        ('def f(a, * args, x): pass\n f(', 'f(a, *args, x)'),
        ('def f(a, *, x): pass\n f(', 'f(a, *, x)'),
        ('def f(*, x= 3,**kwargs): pass\n f(', 'f(*, x=3, **kwargs)'),
        ('def f(x,/,y,* ,z): pass\n f(', 'f(x, /, y, *, z)'),
        ('def f(a, /, *, x=3, **kwargs): pass\n f(', 'f(a, /, *, x=3, **kwargs)'),
    ]
)
def test_tree_signature(Script, environment, code, expected):
    # Only test this in the latest version, because of /
    if environment.version_info < (3, 8):
        pytest.skip()

    sig, = Script(code).call_signatures()
    assert expected == sig._signature.to_string()


def test_pow_signature(Script):
    # See github #1357
    sigs = Script('pow(').call_signatures()
    strings = {sig._signature.to_string() for sig in sigs}
    assert strings == {'pow(x: float, y: float, z: float, /) -> float',
                       'pow(x: float, y: float, /) -> float',
                       'pow(x: int, y: int, z: int, /) -> Any',
                       'pow(x: int, y: int, /) -> Any'}


@pytest.mark.parametrize(
    'start, start_params', [
        ['@dataclass\nclass X:', []],
        ['@dataclass(eq=True)\nclass X:', []],
        [dedent('''
         class Y():
             y: int
         @dataclass
         class X(Y):'''), []],
        [dedent('''
         @dataclass
         class Y():
             y: int
             z = 5
         @dataclass
         class X(Y):'''), ['y']],
    ]
)
def test_dataclass_signature(Script, skip_pre_python37, start, start_params):
    code = dedent('''
            name: str
            foo = 3
            price: float
            quantity: int = 0.0

        X(''')

    code = 'from dataclasses import dataclass\n' + start + code

    sig, = Script(code).call_signatures()
    assert [p.name for p in sig.params] == start_params + ['name', 'price', 'quantity']
    quantity, = sig.params[-1].infer()
    assert quantity.name == 'int'
    price, = sig.params[-2].infer()
    assert price.name == 'float'
