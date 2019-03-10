import os

import pytest


@pytest.mark.parametrize('code', ('import math', 'from math import cos'))
def test_math_is_stub(Script, code):
    s = Script(code)
    cos, = s.goto_definitions()
    wanted = os.path.join('typeshed', 'stdlib', '2and3', 'math.pyi')
    assert cos.module_path.endswith(wanted)

    cos, = s.goto_assignments()
    assert cos.module_path.endswith(wanted)
