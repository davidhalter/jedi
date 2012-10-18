########################################
Jedi - an awesome Python auto-completion
########################################

.. image:: https://secure.travis-ci.org/davidhalter/jedi.png?branch=master
    :target: http://travis-ci.org/davidhalter/jedi
    :alt: Travis-CI build status

**beta testing**

*If you have any comments or feature requests, please tell me! I really want to
know, what you think about Jedi.*

Jedi is an autocompletion tool for Python. It works. With and without syntax
errors. Sometimes it sucks, but that's normal in dynamic languages. But it
sucks less than other tools. It understands almost all of the basic Python
syntax elements including many builtins.

Jedi suports two different goto functions and has support for renaming.
Probably it will also have some support for refactoring some in the future.

Jedi uses a very simple interface to connect with IDE's. As an reference, there
is a VIM implementation, which uses Jedi's autocompletion. However, I encourage
you to use Jedi in your IDEs. Start writing plugins! If there are problems with
licensing, just contact me.

At the moment Jedi can be used as a 
`VIM-Plugin <http://github.com/davidhalter/jedi-vim>`_. So, if you want to test
Jedi for now, you'll have to use VIM. But there are new plugins emerging:

- `Emacs-Plugin <https://github.com/tkf/emacs-jedi>`_ **Under construction**
- `Sublime-Plugin <https://github.com/svaiter/SublimeJEDI>`_ **Under construction**

Here are some pictures:

.. image:: https://github.com/davidhalter/jedi/raw/master/screenshot_complete.png

Completion for almost anything (Ctrl+Space).

.. image:: https://github.com/davidhalter/jedi/raw/master/screenshot_function.png

Display of function/class bodies, docstrings.

.. image:: https://github.com/davidhalter/jedi/raw/master/screenshot_pydoc.png

Pydoc support (with highlighting, Shift+k).

There is also support for goto and renaming.

Get the latest from `github <http://github.com/davidhalter/jedi>`_.


Support
=======

Jedi supports Python 2.5 up to 3.x. There is just one code base, for both
Python 2 and 3.
Jedi supports many of the widely used Python features:

- builtin functions/classes support
- complex module / function / class structures
- ignores syntax and indentation errors
- multiple returns / yields
- tuple assignments / array indexing / dictionary indexing
- exceptions / with-statement
- \*args / \*\*kwargs
- decorators
- descriptors -> property / staticmethod / classmethod
- closures
- generators (yield statement) / iterators
- support for some magic methods: ``__call__``, ``__iter__``, ``__next__``,
  ``__get__``, ``__getitem__``, ``__init__``
- support for list.append, set.add, list.extend, etc.
- (nested) list comprehensions / ternary expressions
- relative imports
- ``getattr()`` / ``__getattr__`` / ``__getattribute__``
- function annotations (py3k feature, are ignored right now, but being parsed.
  I don't know what to do with them.)
- class decorators (py3k feature, are being ignored too, until I find a use
  case, that doesn't work with Jedi)
- simple/usual ``sys.path`` modifications
- ``isinstance`` checks for if/while/assert

However, it does not yet support (and probably will in future versions, because
they are on my todo list):

- manipulations of instances outside the instance variables, without using
  functions

It does not support (and most probably will not in future versions): 

- metaclasses (how could an auto-completion ever support this)
- ``setattr()``
- evaluate ``if`` / ``while``


Caveats
=======

This framework should work for both Python 2/3. However, some things were just
not as *pythonic* in Python 2 as things should be. To keep things simple, some
things have been held back:

- Classes: Always Python 3 like, therefore all classes inherit from ``object``.
- Generators: No ``next`` method. The ``__next__`` method is used instead.
- Exceptions are only looked at in the form of ``Exception as e``, no comma!

Syntax errors and other strange stuff, that is defined differently in the
Python language, may lead to undefined behaviour of the completion. Jedi is
**NOT** a Python compiler, that tries to correct you. It is a tool that wants
to help you. But **YOU** have to know Python, not Jedi.

Importing ``numpy`` can be quite slow sometimes, as well as loading the builtins
the first time. If you want to speed it up, you could write import hooks in
jedi, which preloads this stuff. However, once loaded, this is not a problem
anymore. The same is true for huge modules like ``PySide``, ``wx``, etc.


A little history
================

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There is even an awesome `scene
<http://www.youtube.com/watch?v=5BDO3pyavOY>`_ of Monty Python Jedi's :-). 

But actually the name hasn't so much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *Oh, that worries me*

When it's finished, I hope he'll like it :-)

I actually started Jedi, because there were no good solutions available for
VIM. Most auto-completions just didn't work well. The only good solution was
PyCharm. I just like my good old VIM. Rope was never really intended to be an
auto-completion (and also I really hate project folders for my Python scripts).
It's more of a refactoring suite. So I decided to do my own version of a
completion, which would execute non-dangerous code. But I soon realized, that
this wouldn't work. So I built an extremely recursive thing which understands
many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.


API-Design for IDEs
===================

If you want to set up an IDE with Jedi, you need to ``import jedi``. You should
have the following objects available:

::

    Script(source, line, column, source_path)

``source`` would be the source of your python file/script, separated by new
lines. ``line`` is the current line you want to perform actions on (starting
with line #1 as the first line). ``column`` represents the current
column/indent of the cursor (starting with zero). ``source_path`` should be the
path of your file in the file system.

It returns a script object that contains the relevant information for the other
functions to work without params.

::

    Script().complete

Returns ``api.Completion`` objects. Those objects have got
informations about the completions. More than just names.

::

    Script().goto

Similar to complete. The returned ``api.Definition`` objects contain
information about the definitions found.

::

    Script().get_definition

Mostly used for tests. Like goto, but follows statements and imports and
doesn't break there. You probably don't want to use this function. It's
mostly for testing.

::

    Script().related_names

Returns all names that point to the definition of the name under the
cursor. This is also very useful for refactoring (renaming).

::

    Script().get_in_function_call

Get the ``Function`` object of the call you're currently in, e.g.: ``abs(``
with the cursor at the end would return the builtin ``abs`` function.

::

    NotFoundError

If you use the goto function and no valid identifier (name) is at the
place of the cursor (position). It will raise this exception.

::

    set_debug_function

Sets a callback function for ``debug.py``. This function is called with
multiple text objects, in python 3 you could insert ``print``.

::

    settings

Access to the ``settings.py`` module. The settings are described there.
