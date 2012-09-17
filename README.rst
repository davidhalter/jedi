######################################
Jedi - a clever Python auto-completion
######################################

.. image:: https://secure.travis-ci.org/davidhalter/jedi.png?branch=master
    :target: http://travis-ci.org/davidhalter/jedi
    :alt: Travis-CI build status

**now in alpha testing phase**

*If you have any comments or feature request, please tell me! I really want to
know, what you think about Jedi.*

Jedi is an autocompletion tool for Python. It should work as good as possible
and just ignore syntax errors. Most Python auto-completions really suck,
because they don't understand things like decorators, generators and list
comprehensions. Jedi just sucks less, because it at least understand those
features.

Jedi suports goto and will support some refactorings in the future.
Auto-completion is the core.

Jedi uses a very simple interface to connect with IDE's. As an example, there
is a VIM implementation, which uses Jedi's autocompletion. However, I encourage
you to use Jedi in your IDEs, as soon as a stable version arrives. If there are
problems with licensing, just contact me.

At the moment Jedi can be used as a **VIM-Plugin**. So, if you want to test
Jedi for now, you'll have to use VIM. Just check the chapter on VIM bellow.

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

However, it does not yet support (and probably will in future versions, because
they are on my todo list):

- assert / isinstance
- manipulations of instances outside the instance variables, without using
  functions
- operation support -> ``__mul__``, ``__add__``, etc.

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
of the precognition the Jedi have.

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
this wouldn't work. So I built an extremely recursive thing, that understands
many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need some time, because of its recursive nature.


API-Design for IDEs
===================

If you want to set up an IDE with Jedi, you need to ``import jedi``. You should
have the following objects available:

::

    Script

Returns a script object, that contains the relevant information for the
other functions to work without params. 

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


VIM Plugin
==========

At the moment jedi is also a VIM plugin. It is some sort of reference
implementation for other IDE's.
The VIM plugin is located under ``plugin/jedi.vim``.

You might want to use `pathogen <https://github.com/tpope/vim-pathogen>`_ to
install jedi in VIM. Also you need a VIM version that was compiled with
``+python``, which is typical for most distributions on Linux.

Jedi is automatically initialized. If you don't want that I suggest you
disable the auto-initialization in your ``.vimrc``::

    let g:jedi#auto_initialization = 0

The autocompletion can be used with <ctrl+space>, if you want it to work with
<tab> you can use `supertab <https://github.com/ervandew/supertab>`_.
The goto is by default on <leader g>. If you want to change that::

    let g:jedi#goto_command = "<leader>g"

``get_definition`` is by default on <leader d>. If you want to change that::

    let g:jedi#get_definition_command = "<leader>d"

Showing the pydoc is by default on ``K`` If you want to change that::

    let g:jedi#pydoc = "K"

If you are a person who likes to use VIM-buffers not tabs, you might want to
put that in your ``.vimrc``::

    let g:jedi#use_tabs_not_buffers = 0

Jedi automatically starts the completion, if you type a dot, e.g. ``str.``, if
you don't want this::

    let g:jedi#popup_on_dot = 0

There's some support for refactoring::

    let g:jedi#rename_command = "<leader>r"

And you can list all names that are related (have the same origin)::

    let g:jedi#related_names_command = "<leader>n"
