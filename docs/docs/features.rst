.. include:: ../global.rst

Features and Limitations
========================

Jedi's main API calls and features are:

- Autocompletion: :meth:`.Script.complete`; It's also possible to get it
  working in :ref:`your REPL (IPython, etc.) <repl-completion>`
- Goto/Type Inference: :meth:`.Script.goto` and :meth:`.Script.infer`
- Static Analysis: :meth:`.Script.get_names` and :meth:`.Script.get_syntax_errors`
- Refactorings: :meth:`.Script.rename`, :meth:`.Script.inline`,
  :meth:`.Script.extract_variable` and :meth:`.Script.extract_function`
- Code Search: :meth:`.Script.search` and :meth:`.Project.search`

Basic Features
--------------

- Python 2.7 and 3.5+ support
- Ignores syntax errors and wrong indentation
- Can deal with complex module / function / class structures
- Great ``virtualenv``/``venv`` support
- Works great with Python's :ref:`type hinting <type-hinting>`,
- Understands stub files
- Can infer function arguments for sphinx, epydoc and basic numpydoc docstrings
- Is overall a very solid piece of software that has been refined for a long
  time. Bug reports are very welcome and are usually fixed within a few weeks.


Supported Python Features
-------------------------

|jedi| supports many of the widely used Python features:

- builtins
- returns, yields, yield from
- tuple assignments / array indexing / dictionary indexing / star unpacking
- with-statement / exception handling
- ``*args`` / ``**kwargs``
- decorators / lambdas / closures
- generators / iterators
- descriptors: property / staticmethod / classmethod / custom descriptors
- some magic methods: ``__call__``, ``__iter__``, ``__next__``, ``__get__``,
  ``__getitem__``, ``__init__``
- ``list.append()``, ``set.add()``, ``list.extend()``, etc.
- (nested) list comprehensions / ternary expressions
- relative imports
- ``getattr()`` / ``__getattr__`` / ``__getattribute__``
- function annotations
- simple/typical ``sys.path`` modifications
- ``isinstance`` checks for if/while/assert
- namespace packages (includes ``pkgutil``, ``pkg_resources`` and PEP420 namespaces)
- Django / Flask / Buildout support
- Understands Pytest fixtures


Limitations
-----------

In general Jedi's limit are quite high, but for very big projects or very
complex code, sometimes Jedi intentionally stops type inference, to avoid
hanging for a long time.

Additionally there are some Python patterns Jedi does not support. This is
intentional and below should be a complete list:

- Arbitrary metaclasses: Some metaclasses like enums and dataclasses are
  reimplemented in Jedi to make them work. Most of the time stubs are good
  enough to get type inference working, even when metaclasses are involved.
- ``setattr()``, ``__import__()``
- Writing to some dicts: ``globals()``, ``locals()``, ``object.__dict__``
- Manipulations of instances outside the instance variables without using
  methods 

Performance Issues
~~~~~~~~~~~~~~~~~~

Importing ``numpy`` can be quite slow sometimes, as well as loading the
builtins the first time. If you want to speed things up, you could preload
libriaries in |jedi|, with :func:`.preload_module`. However, once loaded, this
should not be a problem anymore.  The same is true for huge modules like
``PySide``, ``wx``, ``tensorflow``, ``pandas``, etc.

Jedi does not have a very good cache layer. This is probably the biggest and
only architectural `issue <https://github.com/davidhalter/jedi/issues/1059>`_ in
Jedi. Unfortunately it is not easy to change that. Dave Halter is thinking
about rewriting Jedi in Rust, but it has taken Jedi more than 8 years to reach
version 1.0, a rewrite will probably also take years.

Security
--------

For :class:`.Script`
~~~~~~~~~~~~~~~~~~~~

Security is an important topic for |jedi|. By default, no code is executed
within Jedi. As long as you write pure Python, everything is inferred
statically. If you enable ``load_unsafe_extensions=True`` for your
:class:`.Project` and you use builtin modules (``c_builtin``) Jedi will execute
those modules. If you don't trust a code base, please do not enable that
option. It might lead to arbitrary code execution.

For :class:`.Interpreter`
~~~~~~~~~~~~~~~~~~~~~~~~~

If you want security for :class:`.Interpreter`, ``do not`` use it. Jedi does
execute properties and in general is not very careful to avoid code execution.
This is intentional: Most people trust the code bases they have imported,
because at that point a malicious code base would have had code execution
already.

Recipes
-------

Here are some tips on how to use |jedi| efficiently.


.. _type-hinting:

Type Hinting
~~~~~~~~~~~~

If |jedi| cannot detect the type of a function argument correctly (due to the
dynamic nature of Python), you can help it by hinting the type using
one of the following docstring/annotation syntax styles:

**PEP-0484 style**

https://www.python.org/dev/peps/pep-0484/

function annotations

::

    def myfunction(node: ProgramNode, foo: str) -> None:
        """Do something with a ``node``.

        """
        node.| # complete here


assignment, for-loop and with-statement type hints (all Python versions).
Note that the type hints must be on the same line as the statement

::

    x = foo()  # type: int
    x, y = 2, 3  # type: typing.Optional[int], typing.Union[int, str] # typing module is mostly supported
    for key, value in foo.items():  # type: str, Employee  # note that Employee must be in scope
        pass
    with foo() as f:  # type: int
        print(f + 3)

Most of the features in PEP-0484 are supported including the typing module
(for Python < 3.5 you have to do ``pip install typing`` to use these),
and forward references.

You can also use stub files.


**Sphinx style**

http://www.sphinx-doc.org/en/stable/domains.html#info-field-lists

::

    def myfunction(node, foo):
        """Do something with a ``node``.

        :type node: ProgramNode
        :param str foo: foo parameter description

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

**Numpydoc**

https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt

In order to support the numpydoc format, you need to install the `numpydoc
<https://pypi.python.org/pypi/numpydoc>`__ package.

::

    def foo(var1, var2, long_var_name='hi'):
        r"""A one-line summary that does not use variable names or the
        function name.

        ...

        Parameters
        ----------
        var1 : array_like
            Array_like means all those objects -- lists, nested lists,
            etc. -- that can be converted to an array. We can also
            refer to variables like `var1`.
        var2 : int
            The type above can either refer to an actual Python type
            (e.g. ``int``), or describe the type of the variable in more
            detail, e.g. ``(N,) ndarray`` or ``array_like``.
        long_variable_name : {'hi', 'ho'}, optional
            Choices in brackets, default first when optional.

        ...

        """
        var2.| # complete here

A little bit of history
-----------------------

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There's even an awesome `scene
<https://youtu.be/yHRJLIf7wMU>`_ of Monty Python Jedis :-).

But actually the name has not much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *"Oh, that worries me..."*

When it's finished, I hope he'll like it :-)

I actually started Jedi back in 2012, because there were no good solutions
available for VIM.  Most auto-completions just didn't work well. The only good
solution was PyCharm.  But I like my good old VIM. Rope was never really
intended to be an auto-completion (and also I really hate project folders for
my Python scripts).  It's more of a refactoring suite. So I decided to do my
own version of a completion, which would execute non-dangerous code. But I soon
realized, that this wouldn't work. So I built an extremely recursive thing
which understands many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.

Acknowledgements
----------------

- Thanks to all the contributors, see also the ``AUTHORS.txt``.
- Takafumi Arakaki (@tkf) for creating a solid test environment and a lot of
  other things.
- Danilo Bargen (@dbrgn) for general housekeeping and being a good friend :).
- Guido van Rossum (@gvanrossum) for creating the parser generator pgen2
  (originally used in lib2to3).
