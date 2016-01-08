# -*- coding: utf-8    # This file contains Unicode characters.

from textwrap import dedent

import pytest

from jedi._compatibility import u, unicode
from jedi.parser import ParserWithRecovery, load_grammar
from jedi.parser import tree as pt


class TestsFunctionAndLambdaParsing(object):

    FIXTURES = [
        ('def my_function(x, y, z) -> str:\n    return x + y * z\n', {
            'name': 'my_function',
            'call_sig': 'my_function(x, y, z)',
            'params': ['x', 'y', 'z'],
            'annotation': "str",
        }),
        ('lambda x, y, z: x + y * z\n', {
            'name': '<lambda>',
            'call_sig': '<lambda>(x, y, z)',
            'params': ['x', 'y', 'z'],
        }),
    ]

    @pytest.fixture(params=FIXTURES)
    def node(self, request):
        parsed = ParserWithRecovery(load_grammar(), dedent(u(request.param[0])))
        request.keywords['expected'] = request.param[1]
        return parsed.module.subscopes[0]

    @pytest.fixture()
    def expected(self, request, node):
        return request.keywords['expected']
    
    def test_name(self, node, expected):
        assert isinstance(node.name, pt.Name)
        assert unicode(node.name) == u(expected['name'])
    
    def test_params(self, node, expected):
        assert isinstance(node.params, list)
        assert all(isinstance(x, pt.Param) for x in node.params)
        assert [unicode(x.name) for x in node.params] == [u(x) for x in expected['params']]

    def test_is_generator(self, node, expected):
        assert node.is_generator() is expected.get('is_generator', False)

    def test_yields(self, node, expected):
        # TODO: There's a comment in the code noting that the current implementation is incorrect.  This returns an
        # empty list at the moment (not e.g. False).
        if expected.get('yields', False):
            assert node.yields
        else:
            assert not node.yields

    def test_annotation(self, node, expected):
        expected_annotation = expected.get('annotation', None)
        if expected_annotation is None:
            assert node.annotation() is None
        else:
            assert node.annotation().value == expected_annotation

    def test_get_call_signature(self, node, expected):
        assert node.get_call_signature() == expected['call_sig']

    def test_doc(self, node, expected):
        assert node.doc == expected.get('doc') or (expected['call_sig'] + '\n\n')
