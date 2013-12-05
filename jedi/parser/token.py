""" Efficient representation of tokens

We want to have a token_list and start_position for everything the
tokenizer returns. Therefore we need a memory efficient class. We
found that a flat object with slots is the best. The Token object is
that plus indexing and string backwards compatibility.

"""

class Token(object):
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

    # Backward compatibility
    def __str__(self):
        return str(self.token)

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
            raise IndexError()

    # Backward compatibility
    def __setitem__(self, key, value):
        # setitem analogous to
        if key   == 0:
            self.token_type       = value
        elif key == 1:
            self.token            = value
        elif key == 2:
            self.start_pos_line   = value[0]
            self.start_pos_col    = value[1]
        else:
            raise IndexError()

    # Backward compatibility
    def __getattr__(self, attr):
        # Expose the missing start_pos attribute
        if attr == "start_pos":
            return (self.start_pos_line, self.start_pos_col)
        else:
            raise AttributeError(
                "type '%s' has no attriubte '%s'" % (
                    type(self),
                    attr
                )
            )

    # Make cache footprint smaller
    def __getstate__(self):
        return tuple(self)

    def __setstate__(self, state):
        for i in range(len(state)):
            self[i] = state[i]
