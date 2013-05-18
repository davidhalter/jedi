"""
Utilities for end-users.
"""

from rlcompleter import Completer

from jedi import Interpreter


class JediRLCompleter(Completer):

    def _jedi_matches(self, text):
        completions = Interpreter(text, [self.namespace]).completions()
        return [text + c.complete for c in completions]

    @staticmethod
    def _split_for_default_matcher(text, delims='()'):
        """
        Split `text` before passing it to :meth:`Completer.attr_matches` etc.

        >>> JediRLCompleter._split_for_default_matcher('f(')
        ('f(', '')
        >>> JediRLCompleter._split_for_default_matcher('f().g')
        ('f()', '.g')

        """
        import re
        m = re.match(r"(.*[{0}])([^{0}]*)".format(re.escape(delims)), text)
        if not m:
            return ('', text)
        return m.groups()

    def _find_matches(self, default_matcher, text):
        """
        Common part for :meth:`attr_matches` and :meth:`global_matches`.

        Try `default_matcher` first and return what it returns if
        it is not empty.  Otherwise, try :meth:`_jedi_matches`.

        :arg default_matcher: :meth:`.Completer.attr_matches` or
                              :meth:`.Completer.global_matches`.
        :arg str text: code to complete
        """
        (pre, body) = self._split_for_default_matcher(text)
        matches = default_matcher(self, body)
        if matches:
            return [pre + m for m in matches]
        return self._jedi_matches(text)

    def attr_matches(self, text):
        # NOTE: Completer is old type class so `super` cannot be used here
        return self._find_matches(Completer.attr_matches, text)

    def global_matches(self, text):
        # NOTE: Completer is old type class so `super` cannot be used here
        return self._find_matches(Completer.global_matches, text)


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
