"""
Utilities for end-users.
"""

from __future__ import absolute_import
import __main__

from jedi import Interpreter

class JediRL():
    def __init__(self, namespace_module):
        self.namespace_module = namespace_module

    def complete(self, text, state):
        """
        This complete stuff is pretty weird, a generator would make
        a lot more sense, but probably due to backwards compatibility
        this is still the way how it works.

        The only important part is stuff in the ``state == 0`` flow,
        everything else has been copied from the ``rlcompleter`` std.
        library module.
        """
        if state == 0:
            import os, sys
            sys.path.insert(0, os.getcwd())
            # Calling python doesn't have a path, so add to sys.path.
            try:
                interpreter = Interpreter(text, [self.namespace_module.__dict__])

                path, dot, like = interpreter._get_completion_parts()
                before = text[:len(text) - len(like)]
                completions = interpreter.completions()
            finally:
                sys.path.pop(0)

            self.matches = [before + c.name_with_symbols for c in completions]
        try:
            return self.matches[state]
        except IndexError:
            return None

def setup_readline(namespace_module=__main__, combine_old_completer=False):
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
        if hasattr(__main__, 'get_ipython'):
            # We are in IPython. IPython resets the readline completer with
            # each prompt, which we don't want, so let's disable that.
            ip = __main__.get_ipython()
            if combine_old_completer:
                # Try to merge IPython completion and Jedi completion
                ip.set_readline_completer()
            ip.has_readline = False
        old_completer = readline.get_completer()
        completer = JediRL(namespace_module).complete
        if old_completer and combine_old_completer:
            completer = combine_completers(completer, old_completer)
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
        # jedi itself does the case matching
        readline.parse_and_bind("set completion-ignore-case on")
        # because it's easier to hit the tab just once
        readline.parse_and_bind("set show-all-if-unmodified")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        # don't repeat all the things written in the readline all the time
        readline.parse_and_bind("set completion-prefix-display-length 2")
        # No delimiters, Jedi handles that.
        readline.set_completer_delims('')

def combine_completers(first, second, firststate=0):
    """
    Returns a function that calls completer first then completer second,
    assuming first stops after firststate.
    """
    # firststate is the state that JediRL.complete stops after. Right now, it
    # is just 0.
    def completer(text, state):
        if state <= firststate:
            return first(text, state)
        else:
            return second(text, state - firststate)
    return completer
