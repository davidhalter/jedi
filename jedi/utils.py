"""
Utilities for end-users.
"""

import sys

from jedi import Interpreter


def readline_complete(text, state):
    """
    Function to be passed to :func:`readline.set_completer`.

    Usage::

        import readline
        readline.set_completer(readline_complete)

    """
    ns = vars(sys.modules['__main__'])
    completions = Interpreter(text, [ns]).completions()
    try:
        return text + completions[state].complete
    except IndexError:
        return None


def setup_readline():
    """
    Install Jedi completer to :mod:`readline`.
    """
    try:
        import readline
    except ImportError:
        print("Module readline not available.")
    else:
        readline.set_completer(readline_complete)
        readline.parse_and_bind("tab: complete")

        # Default delimiters minus "()":
        readline.set_completer_delims(' \t\n`~!@#$%^&*-=+[{]}\\|;:\'",<>/?')
