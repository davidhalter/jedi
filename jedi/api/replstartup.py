"""
To use Jedi completion in Python interpreter, add the following in your shell
setup (e.g., ``.bashrc``). Jedi configures the classic readline shell and
Python 3.13+'s new ``_pyrepl`` shell when those hooks are available. If
completion still does not work in your environment, try
``PYTHON_BASIC_REPL=1`` to force the classic REPL or use IPython instead::

    export PYTHONSTARTUP="$(python -m jedi repl)"

Then you will be able to use Jedi completer in your Python interpreter::

    $ python
    Python 3.14.0+ (default, Jul 20 2020, 22:15:08)
    [GCC 4.6.1] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> import os
    >>> os.path.join('a', 'b').split().in<TAB>            # doctest: +SKIP
    ..dex   ..sert

"""
import jedi.utils
from jedi import __version__ as __jedi_version__

print('REPL completion using Jedi %s' % __jedi_version__)
jedi.utils.setup_readline(fuzzy=False)

del jedi

# Note: try not to do many things here, as it will contaminate global
# namespace of the interpreter.
