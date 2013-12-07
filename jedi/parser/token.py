# -*- coding: utf-8 -*-
""" Efficient representation of tokens

We want to have a token_list and start_position for everything the
tokenizer returns. Therefore we need a memory efficient class. We
found that a flat object with slots is the best.
"""

from jedi._compatibility import utf8, unicode


class Token(object):
    """The token object is an efficient representation of the structure
    (token_type, token, (start_pos_line, start_pos_col)). It has indexer
    methods that maintain compatibility to existing code that expects the above
    structure.

    >>> tuple(Token(1,2,3,4))
    (1, 2, (3, 4))
    >>> unicode(Token(1, "test", 1, 1)) == "test"
    True
    >>> repr(Token(1, "test", 1, 1))
    "<Token: (1, 'test', (1, 1))>"
    >>> Token(1, 2, 3, 4).__getstate__()
    (1, 2, 3, 4)
    >>> a = Token(0, 0, 0, 0)
    >>> a.__setstate__((1, 2, 3, 4))
    >>> a
    <Token: (1, 2, (3, 4))>
    >>> a[2] = (2, 1)
    >>> a
    <Token: (1, 2, (2, 1))>
    >>> a.start_pos
    (2, 1)
    >>> a.token
    2
    >>> a.start_pos = (3, 4)
    >>> a
    <Token: (1, 2, (3, 4))>
    >>> a.start_pos
    (3, 4)
    >>> a.start_pos_col
    4
    >>> Token.from_tuple((6, 5, (4, 3)))
    <Token: (6, 5, (4, 3))>
    >>> unicode(Token(1, utf8("😷"), 1 ,1)) + "p" == utf8("😷p")
    True
    """
    __slots__ = [
        "token_type", "token", "start_pos_line", "start_pos_col"
    ]

    @classmethod
    def from_tuple(cls, tp):
        return Token(tp[0], tp[1], tp[2][0], tp[2][1])

    def __init__(
        self, token_type, token, start_pos_line, start_pos_col
    ):
        self.token_type     = token_type
        self.token          = token
        self.start_pos_line = start_pos_line
        self.start_pos_col  = start_pos_col

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, tuple(self))

    # Backward compatibility py2
    def __unicode__(self):
        return unicode(self.token)

    # Backward compatibility py3
    def __str__(self):
        return unicode(self.token)

    # Backward compatibility
    def __getitem__(self, key):
        # Builds the same structure as tuple used to have
        if key   == 0:
            return self.token_type
        elif key == 1:
            return self.token
        elif key == 2:
            return (self.start_pos_line, self.start_pos_col)
        else:
            raise IndexError("list index out of range")

    # Backward compatibility
    def __setitem__(self, key, value):
        # setitem analogous to getitem
        if key   == 0:
            self.token_type       = value
        elif key == 1:
            self.token            = value
        elif key == 2:
            self.start_pos_line   = value[0]
            self.start_pos_col    = value[1]
        else:
            raise IndexError("list index out of range")

    # Backward compatibility
    def __getattr__(self, attr):
        # Expose the missing start_pos attribute
        if attr == "start_pos":
            return (self.start_pos_line, self.start_pos_col)
        else:
            return object.__getattr__(self, attr)

    def __setattr__(self, attr, value):
        # setattr analogous to getattr for symmetry
        if attr == "start_pos":
            self.start_pos_line = value[0]
            self.start_pos_col  = value[1]
        else:
            object.__setattr__(self, attr, value)

    # Make cache footprint smaller for faster unpickling
    def __getstate__(self):
        return (
            self.token_type,
            self.token,
            self.start_pos_line,
            self.start_pos_col,
        )

    def __setstate__(self, state):
        self.token_type     = state[0]
        self.token          = state[1]
        self.start_pos_line = state[2]
        self.start_pos_col  = state[3]
