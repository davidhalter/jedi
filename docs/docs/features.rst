.. include:: ../global.rst

Features and Caveats
====================

|jedi| supports many of the widely used Python features:


General Features
----------------

- python 2.6+ and 3.2+ support
- ignores syntax errors and wrong indentation
- can deal with complex module / function / class structures
- virtualenv support
- can infer function arguments from sphinx and epydoc docstrings (:ref:`type
  hinting <type-hinting>`)


Supported Python Features
-------------------------

- builtins
- multiple returns or yields
- tuple assignments / array indexing / dictionary indexing
- with-statement / exception handling
- ``*args`` / ``**kwargs``
- decorators / lambdas / closures
- generators / iterators
- some descriptors: property / staticmethod / classmethod
- some magic methods: ``__call__``, ``__iter__``, ``__next__``, ``__get__``,
  ``__getitem__``, ``__init__``
- ``list.append()``, ``set.add()``, ``list.extend()``, etc.
- (nested) list comprehensions / ternary expressions
- relative imports
- ``getattr()`` / ``__getattr__`` / ``__getattribute__``
- function annotations (py3k feature, are ignored right now, but being parsed.
  I don't know what to do with them.)
- class decorators (py3k feature, are being ignored too, until I find a use
  case, that doesn't work with |jedi|)
- simple/usual ``sys.path`` modifications
- ``isinstance`` checks for if/while/assert
- namespace packages (includes ``pkgutil`` and ``pkg_resources`` namespaces)


Unsupported Features
--------------------

Not yet implemented:

- manipulations of instances outside the instance variables without using
  methods

Will probably never be implemented:

- metaclasses (how could an auto-completion ever support this)
- ``setattr()``, ``__import__()``
- writing to some dicts: ``globals()``, ``locals()``, ``object.__dict__``
- evaluating ``if`` / ``while`` / ``del``


Caveats
-------

**Malformed Syntax**

Syntax errors and other strange stuff may lead to undefined behaviour of the
completion. |jedi| is **NOT** a Python compiler, that tries to correct you. It
is a tool that wants to help you. But **YOU** have to know Python, not |jedi|.

**Legacy Python 2 Features**

This framework should work for both Python 2/3. However, some things were just
not as *pythonic* in Python 2 as things should be. To keep things simple, some
older Python 2 features have been left out:

- Classes: Always Python 3 like, therefore all classes inherit from ``object``.
- Generators: No ``next()`` method. The ``__next__()`` method is used instead.

**Slow Performance**

Importing ``numpy`` can be quite slow sometimes, as well as loading the
builtins the first time. If you want to speed things up, you could write import
hooks in |jedi|, which preload stuff. However, once loaded, this is not a
problem anymore.  The same is true for huge modules like ``PySide``, ``wx``,
etc.

**Security**

Security is an important issue for |jedi|. Therefore no Python code is
executed.  As long as you write pure python, everything is evaluated
statically. But: If you use builtin modules (``c_builtin``) there is no other
option than to execute those modules. However: Execute isn't that critical (as
e.g. in pythoncomplete, which used to execute *every* import!), because it
means one import and no more.  So basically the only dangerous thing is using
the import itself. If your ``c_builtin`` uses some strange initializations, it
might be dangerous. But if it does you're screwed anyways, because eventualy
you're going to execute your code, which executes the import.


Recipes
-------

Here are some tips on how to use |jedi| efficiently.


.. _type-hinting:

Type Hinting
~~~~~~~~~~~~

If |jedi| cannot detect the type of a function argument correctly (due to the
dynamic nature of Python), you can help it by hinting the type using
Sphinx-style info field lists or Epydoc docstrings.

**Sphinx style**

http://sphinx-doc.org/domains.html#info-field-lists

::

    def myfunction(node):
        """Do something with a ``node``.

        :type node: ProgramNode

        """
        node.| # complete here

**Epydoc**

http://epydoc.sourceforge.net/manual-fields.html

::

    def myfunction(node):
        """Do something with a ``node``.

        @type node: ProgramNode

        """
        node.| # complete here

A little history
----------------

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There's even an awesome `scene
<http://www.youtube.com/watch?v=5BDO3pyavOY>`_ of Monty Python Jedis :-).

But actually the name hasn't so much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *"Oh, that worries me..."*

When it's finished, I hope he'll like it :-)

I actually started Jedi, because there were no good solutions available for VIM.
Most auto-completions just didn't work well. The only good solution was PyCharm.
But I like my good old VIM. Rope was never really intended to be an
auto-completion (and also I really hate project folders for my Python scripts).
It's more of a refactoring suite. So I decided to do my own version of a
completion, which would execute non-dangerous code. But I soon realized, that
this wouldn't work. So I built an extremely recursive thing which understands
many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.
