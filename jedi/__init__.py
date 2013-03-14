"""
Jedi is an autocompletion tool for Python that can be used in IDEs/editors.
Jedi works. Jedi is fast. It understands all of the basic Python syntax
elements including many builtin functions.

Additionaly, Jedi suports two different goto functions and has support for
renaming as well as Pydoc support and some other IDE features.

Jedi uses a very simple API to connect with IDE's. There's a reference
implementation as a `VIM-Plugin <http://github.com/davidhalter/jedi-vim>`_,
which uses Jedi's autocompletion.  I encourage you to use Jedi in your IDEs.
It's really easy. If there are any problems (also with licensing), just contact
me.

To give you a simple example how you can use the Jedi library, here is an
example for the autocompletion feature:

>>> import jedi
>>> source = '''
... import datetime
... datetime.da'''
>>> script = jedi.Script(source, 3, len('datetime.da'), 'example.py')
>>> script
<Script: 'example.py'>
>>> completions = script.complete()
>>> completions                                         #doctest: +ELLIPSIS
[<Completion: date>, <Completion: datetime>, ...]
>>> print(completions[0].complete)
te
>>> print(completions[0].word)
date

As you see Jedi is pretty simple and allows you to concentrate on writing a
good text editor, while still having very good IDE features for Python.
"""

from jedi.api import *  # Python 2.5 does not support `from .api import *`
from . import settings

from .deferredimport import import_all
import_all()
del import_all
