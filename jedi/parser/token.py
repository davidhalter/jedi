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
    >>> a.start_pos
    (3, 4)
    >>> a.token
    2
    >>> a.start_pos_col
    4
    >>> Token.from_tuple((6, 5, (4, 3)))
    <Token: (6, 5, (4, 3))>
    >>> unicode(Token(1, utf8("😷"), 1 ,1)) + "p" == utf8("😷p")
    True
    """
    __slots__ = [
        "_token_type", "_token", "_start_pos_line", "_start_pos_col"
    ]

    @classmethod
    def from_tuple(cls, tp):
        return Token(tp[0], tp[1], tp[2][0], tp[2][1])

    def __init__(
        self, token_type, token, start_pos_line, start_pos_col
    ):
        self._token_type     = token_type
        self._token          = token
        self._start_pos_line = start_pos_line
        self._start_pos_col  = start_pos_col

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

    @property
    def token_type(self):
        return self._token_type

    @property
    def token(self):
        return self._token

    @property
    def start_pos_line(self):
        return self._start_pos_line

    @property
    def start_pos_col(self):
        return self._start_pos_col

    # Backward compatibility
    @property
    def start_pos(self):
        return (self.start_pos_line, self.start_pos_col)

    @property
    def end_pos(self):
        """Returns end position respecting multiline tokens."""
        end_pos_line     = self.start_pos_line
        lines            = unicode(self).split('\n')
        end_pos_line    += len(lines) - 1
        end_pos_col      = self.start_pos_col
        # Check for multiline token
        if self.start_pos_line == end_pos_line:
            end_pos_col += len(lines[-1])
        else:
            end_pos_col  = len(lines[-1])
        return (end_pos_line, end_pos_col)

    # Make cache footprint smaller for faster unpickling
    def __getstate__(self):
        return (
            self.token_type,
            self.token,
            self.start_pos_line,
            self.start_pos_col,
        )

    def __setstate__(self, state):
        self._token_type     = state[0]
        self._token          = state[1]
        self._start_pos_line = state[2]
        self._start_pos_col  = state[3]
