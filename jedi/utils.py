"""
Utilities for end-users.
"""

from __future__ import absolute_import
import __main__

from jedi import Interpreter


def setup_readline():
    """
    Install Jedi completer to :mod:`readline`.

    This function setups :mod:`readline` to use Jedi in Python interactive
    shell.  If you want to use a custom ``PYTHONSTARTUP`` file (typically
    ``$HOME/.pythonrc.py``), you can add this piece of code::

        try:
            from jedi.utils import setup_readline
            setup_readline()
        except ImportError:
            # Fallback to the stdlib readline completer if it is installed.
            # Taken from http://docs.python.org/2/library/rlcompleter.html
            print("Jedi is not installed, falling back to readline")
            try:
                import readline
                import rlcompleter
                readline.parse_and_bind("tab: complete")
            except ImportError:
                print("Readline is not installed either. No tab completion is enabled.")

    This will fallback to the readline completer if Jedi is not installed.
    The readline completer will only complete names in the global namespace,
    so for example,

    >>> ran<TAB> # doctest: +SKIP

    will complete to ``range``

    with both Jedi and readline, but

    >>> range(10).cou<TAB> # doctest: +SKIP

    will show complete to ``range(10).count`` only with Jedi.

    You'll also need to add ``export PYTHONSTARTUP=$HOME/.pythonrc.py`` to
    your shell profile (usually ``.bash_profile`` or ``.profile`` if you use
    bash).

    """
    try:
        import readline
    except ImportError:
        print("Module readline not available.")
    else:
        class JediRL():
            def complete(self, text, state):
                """
                This complete stuff is pretty weird, a generator would make
                a lot more sense, but probably due to backwards compatibility
                this is still the way how it works.

                The only important part is the ``Interpreter`` call, everything
                else hsa been copied from the ``rlcompleter`` std. library
                module.
                """
                if state == 0:
                    namespace = __main__.__dict__
                    completions = Interpreter(text, [namespace]).completions()
                    self.matches = [text + c.complete for c in completions]
                try:
                    return self.matches[state]
                except IndexError:
                    return None

        readline.set_completer(JediRL().complete)

        readline.parse_and_bind("tab: complete")
        # No delimiters, Jedi handles that.
        readline.set_completer_delims('')
