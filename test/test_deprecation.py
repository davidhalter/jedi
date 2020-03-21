# -*- coding: utf-8 -*-
import warnings

import pytest

from jedi._compatibility import u


@pytest.fixture(autouse=True)
def check_for_warning(recwarn):
    warnings.simplefilter("always")
    with pytest.warns(DeprecationWarning):
        yield


def test_goto_definitions(Script):
    int_, = Script('x = 1\nx, y\ny', line=2, column=0).goto_definitions()
    assert int_.name == 'int'


def test_completions(Script):
    c1, c2 = Script('foobar = 1\nfoobaz= 2\nfoobaz, ffff\nfool = 3', line=3, column=3).completions()
    assert c1.name == 'foobar'
    assert c2.name == 'foobaz'


def test_goto_assignments(Script):
    int_, = Script('x = 1\nx, y\ny', line=2, column=0).goto_assignments()
    assert int_.get_line_code() == 'x = 1\n'


def test_usages(Script):
    d1, d2 = Script('x = 1\nx, y\ny', line=2, column=0).usages()
    assert d1.name == 'x'
    assert d1.line == 1
    assert d2.name == 'x'
    assert d2.line == 2


def test_call_signatures(Script):
    d1, = Script('abs(float(\nstr(', line=1, column=4).call_signatures()
    assert d1.name == 'abs'


def test_encoding_parameter(Script):
    name = u('hö')
    s = Script(name.encode('latin-1'), encoding='latin-1')
    assert s._module_node.get_code() == name
