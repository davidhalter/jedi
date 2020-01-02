from textwrap import dedent

import pytest


def test_error_leaf_keyword_doc(Script):
    d, = Script("or").help(1, 1)
    assert len(d.docstring()) > 100
    assert d.name == 'or'


def test_error_leaf_operator_doc(Script):
    d, = Script("==").help()
    assert len(d.docstring()) > 100
    assert d.name == '=='


def test_keyword_completion(Script):
    k = Script("fro").complete()[0]
    imp_start = 'The "import'
    assert k.docstring(raw=True).startswith(imp_start)
    assert k.docstring().startswith(imp_start)


def test_import_keyword(Script):
    d, = Script("import x").help(column=0)
    assert d.docstring().startswith('The "import" statement')
    # unrelated to #44


def test_import_keyword_with_gotos(goto_or_infer):
    assert not goto_or_infer("import x", column=0)


def test_operator_doc(Script):
    d, = Script("a == b").help(1, 3)
    assert len(d.docstring()) > 100


def test_lambda(Script):
    d, = Script('lambda x: x').help(column=0)
    assert d.type == 'keyword'
    assert d.docstring().startswith('Lambdas\n*******')


@pytest.mark.parametrize(
    'code, kwargs', [
        ('?', {}),
        ('""', {}),
        ('"', {}),
    ]
)
def test_help_no_returns(Script, code, kwargs):
    assert not Script(code).help(**kwargs)


@pytest.mark.parametrize(
    'to_execute, expected_doc', [
        ('X.x', 'Yeah '),
        ('X().x', 'Yeah '),
        ('X.y', 'f g '),
        ('X.z', '<lambda>(x)'),
    ]
)
def test_attribute_docstrings(goto_or_help, expected_doc, to_execute):
    code = dedent('''\
        class X:
            "ha"
            x = 3
            """ Yeah """
            y = 5
            "f g "
            z = lambda x: 1
        ''')

    d, = goto_or_help(code + to_execute)
    assert d.docstring() == expected_doc
