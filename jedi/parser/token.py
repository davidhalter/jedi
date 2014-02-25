# -*- coding: utf-8 -*-
""" Efficient representation of tokens

We want to have a token_list and start_position for everything the
tokenizer returns. Therefore we need a memory efficient class. We
found that a flat object with slots is the best.
"""
from inspect import cleandoc
from ast import literal_eval

from jedi._compatibility import unicode
from jedi.parser.tokenize import Token


class TokenDocstring(Token):
    """A string token that is a docstring.

    as_string() will clean the token representing the docstring.
    """
    __slots__ = ()

    def __init__(self, token=None, state=None):
        if token:
            self.__setstate__(token.__getstate__())
        else:
            self.__setstate__(state)

    @classmethod
    def fake_docstring(cls, docstr):
        # TODO: fixme when tests are up again
        return TokenDocstring(state=(0, '"""\n%s\n"""' % docstr, 0, 0))

    def as_string(self):
        """Returns a literal cleaned version of the token"""
        return unicode(cleandoc(literal_eval(self.string)))
