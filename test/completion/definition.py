"""
Fallback to callee definition when definition not found.
- https://github.com/davidhalter/jedi/issues/131
- https://github.com/davidhalter/jedi/pull/149
"""

#? isinstance
isinstance(
)

#? isinstance
isinstance(None,
)

#? isinstance
isinstance(None, 
)

# Note: len('isinstance(') == 11
#? 11 isinstance
isinstance()

# Note: len('isinstance(None,') == 16
##? 16 isinstance
isinstance(None,)

# Note: len('isinstance(None,') == 16
##? 16 isinstance
isinstance(None, )

# Note: len('isinstance(None, ') == 17
##? 17 isinstance
isinstance(None, )

# Note: len('isinstance( ') == 12
##? 12 isinstance
isinstance( )
