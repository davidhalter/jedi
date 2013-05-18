"""
Utilities for end-users.
"""

from rlcompleter import Completer

from jedi import Interpreter


class JediRLCompleter(Completer):

    def attr_matches(self, text):
        if '(' in text or ')' in text:
            completions = Interpreter(text, [self.namespace]).completions()
            return [text + c.complete for c in completions]
        else:
            # NOTE: Completer is old type class
            return Completer.attr_matches(self, text)


def setup_readline():
    """
    Install Jedi completer to :mod:`readline`.

    This function setups :mod:`readline` to use Jedi in Python interactive
    shell.  If you want to use custom ``PYTHONSTARTUP`` file, you can call
    this function like this:

    >>> from jedi.utils import setup_readline
    >>> setup_readline()

    """
    try:
        import readline
    except ImportError:
        print("Module readline not available.")
    else:
        readline.set_completer(JediRLCompleter().complete)
        readline.parse_and_bind("tab: complete")

        # Default delimiters minus "()":
        readline.set_completer_delims(' \t\n`~!@#$%^&*-=+[{]}\\|;:\'",<>/?')
