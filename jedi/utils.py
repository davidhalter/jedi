"""
Utilities for end-users.
"""

from __future__ import absolute_import, print_function
import __main__

import sys
import re

from jedi import Interpreter


def setup_readline(namespace_module=__main__):
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
    class JediRL(object):
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
                    interpreter = Interpreter(text, [namespace_module.__dict__])

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

    try:
        import readline
    except ImportError:
        print("Module readline not available.")
    else:
        # Taken from SymPy (sympy/printing/pretty/stringpict.py)
        def terminal_width():
            """Return the terminal width if possible, otherwise return 0.
            """
            ncols = 0
            try:
                import curses
                import io
                try:
                    curses.setupterm()
                    ncols = curses.tigetnum('cols')
                except AttributeError:
                    # windows curses doesn't implement setupterm or tigetnum
                    # code below from
                    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/440694
                    from ctypes import windll, create_string_buffer
                    # stdin handle is -10
                    # stdout handle is -11
                    # stderr handle is -12
                    h = windll.kernel32.GetStdHandle(-12)
                    csbi = create_string_buffer(22)
                    res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
                    if res:
                        import struct
                        (bufx, bufy, curx, cury, wattr,
                         left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
                        ncols = right - left + 1
                except curses.error:
                    pass
                except io.UnsupportedOperation:
                    pass
            except (ImportError, TypeError):
                pass
            return ncols

        TERM_WIDTH = terminal_width() or 80 # TODO: Better logic here

        # For now, just show the end of the completion that's a keyword.
        # re.UNICODE is technically not correct in Python 2, but it shouldn't hurt
        identifier = re.compile(r"[^\d\W]\w*$", re.UNICODE)

        import rl.readline as readline
        def display_matches_hook(substitution, matches, longest_match_length):
            rematch = identifier.search(substitution)
            pos = rematch.start() if rematch else len(substitution)
            # At least spaces between matches
            newmatches = [match[pos:] for match in matches]
            try:
                import rl
                rl.readline.display_match_list(substitution, newmatches,
                    longest_match_length - pos)
            except Exception as e:
                print(e)
            rl.readline.redisplay(force=True)

        readline.set_completion_display_matches_hook(display_matches_hook)
        readline.set_completer(JediRL().complete)
        readline.parse_and_bind("tab: complete")
        # jedi itself does the case matching
        readline.parse_and_bind("set completion-ignore-case on")
        # because it's easier to hit the tab just once
        readline.parse_and_bind("set show-all-if-unmodified")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        # don't repeat all the things written in the readline all the time
        #readline.parse_and_bind("set completion-prefix-display-length 2")
        # No delimiters, Jedi handles that.
        readline.set_completer_delims('')
