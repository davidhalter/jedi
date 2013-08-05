"""
Utilities for end-users.
"""

from rlcompleter import Completer

from jedi import Interpreter


_NON_DELIMS = ' \t\n()'
"""
:class:`rcompleter.Completer` assumes these characters to be delimiter
(i.e., :meth:`rcompleter.Completer.complete` does not expect these
characters) but :class:`JediRLCompleter` can handle them.
"""

try:
    import readline
except ImportError:
    pass
else:
    _READLINE_DEFAULT_DELIMS = readline.get_completer_delims()
    _READLINE_JEDI_DELIMS = ''.join(
        set(_READLINE_DEFAULT_DELIMS) - set(_NON_DELIMS))


class JediRLCompleter(Completer):

    """
    :class:`rlcompleter.Completer` enhanced by Jedi.

    This class tries matchers defined in :class:`.Completer` first.
    If they fail, :class:`jedi.Interpreter` is used.

    >>> import os
    >>> completer = JediRLCompleter(locals())
    >>> completer.complete('os.path.joi', 0)   # completion w/o Jedi
    'os.path.join('
    >>> completer.complete('os.path.join().s', 0)   # completion with Jedi
    'os.path.join().split'

    """

    def _jedi_matches(self, text):
        completions = Interpreter(text, [self.namespace]).completions()
        return [text + c.complete for c in completions]

    @staticmethod
    def _split_for_default_matcher(text, delims=_NON_DELIMS):
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
    shell.  If you want to use a custom ``PYTHONSTARTUP`` file (typically
    ``$HOME/.pythonrc.py``), you can add this piece of code:

    >>> try:
    >>>     from jedi.utils import setup_readline
    >>>     setup_readline()
    >>> except ImportError:
    >>>     print('Install Jedi with pip! No autocompletion otherwise.')

    """
    try:
        import readline
    except ImportError:
        print("Module readline not available.")
    else:
        readline.set_completer(JediRLCompleter().complete)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(_READLINE_JEDI_DELIMS)
