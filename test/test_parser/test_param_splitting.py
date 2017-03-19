'''
To make the life of any analysis easier, we are generating Param objects
instead of simple parser objects.
'''

from textwrap import dedent

from jedi.parser.python import parse


def assert_params(param_string, **wanted_dct):
    source = dedent('''
    def x(%s):
        pass
    ''') % param_string

    module = parse(source)
    funcdef = module.subscopes[0]
    dct = dict((p.name.value, p.default and p.default.get_code())
               for p in funcdef.params)
    assert dct == wanted_dct
    assert module.get_code() == source


def test_split_params_with_separation_star():
    assert_params(u'x, y=1, *, z=3', x=None, y='1', z='3')
    assert_params(u'*, x', x=None)
    assert_params(u'*')


def test_split_params_with_stars():
    assert_params(u'x, *args', x=None, args=None)
    assert_params(u'**kwargs', kwargs=None)
    assert_params(u'*args, **kwargs', args=None, kwargs=None)
