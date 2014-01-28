"""
Helpers for the API
"""
from jedi import debug
from jedi.evaluate import helpers
from jedi.parser import representation as pr


def func_call_and_param_index(user_stmt, position):
    debug.speed('func_call start')
    call, index = None, 0
    if call is None:
        if user_stmt is not None and isinstance(user_stmt, pr.Statement):
            call, index, _ = helpers.search_call_signatures(user_stmt, position)
    debug.speed('func_call parsed')
    return call, index
