# -*- coding: utf-8    # This file contains Unicode characters.

from textwrap import dedent

import pytest

from jedi.parser.python import parse
from jedi.parser.python import tree


class TestsFunctionAndLambdaParsing(object):

    FIXTURES = [
        ('def my_function(x, y, z) -> str:\n    return x + y * z\n', {
            'name': 'my_function',
            'params': ['x', 'y', 'z'],
            'annotation': "str",
        }),
        ('lambda x, y, z: x + y * z\n', {
            'name': '<lambda>',
            'params': ['x', 'y', 'z'],
        }),
    ]

    @pytest.fixture(params=FIXTURES)
    def node(self, request):
        parsed = parse(dedent(request.param[0]))
        request.keywords['expected'] = request.param[1]
        child = parsed.children[0]
        if child.type == 'simple_stmt':
            child = child.children[0]
        return child

    @pytest.fixture()
    def expected(self, request, node):
        return request.keywords['expected']

    def test_name(self, node, expected):
        if node.type != 'lambdef':
            assert isinstance(node.name, tree.Name)
            assert node.name.value == expected['name']

    def test_params(self, node, expected):
        assert isinstance(node.params, list)
        assert all(isinstance(x, tree.Param) for x in node.params)
        assert [str(x.name.value) for x in node.params] == [x for x in expected['params']]

    def test_is_generator(self, node, expected):
        assert node.is_generator() is expected.get('is_generator', False)

    def test_yields(self, node, expected):
        # TODO: There's a comment in the code noting that the current
        # implementation is incorrect.
        assert node.is_generator() == expected.get('yields', False)

    def test_annotation(self, node, expected):
        expected_annotation = expected.get('annotation', None)
        if expected_annotation is None:
            assert node.annotation is None
        else:
            assert node.annotation.value == expected_annotation
