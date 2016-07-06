'''
To make the life of any analysis easier, we are generating Param objects
instead of simple parser objects.
'''

from textwrap import dedent

from jedi.parser import Parser, load_grammar


def assert_params(param_string, **wanted_dct):
    source = dedent('''
    def x(%s):
        pass
    ''') % param_string

    parser = Parser(load_grammar(), dedent(source))
    funcdef = parser.get_parsed_node().subscopes[0]
    dct = dict((p.name.value, p.default and p.default.get_code())
               for p in funcdef.params)
    assert dct == wanted_dct
    assert parser.get_parsed_node().get_code() == source


def test_split_params_with_separation_star():
    assert_params('x, y=1, *, z=3', x=None, y='1', z='3')
    assert_params('*, x', x=None)
    assert_params('*')


def test_split_params_with_stars():
    assert_params('x, *args', x=None, args=None)
    assert_params('**kwargs', kwargs=None)
    assert_params('*args, **kwargs', args=None, kwargs=None)
