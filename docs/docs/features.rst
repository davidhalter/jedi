.. include:: ../global.rst

Features and Caveats
====================

Jedi's main API calls and featuresare:

- Autocompletion: :meth:`.Script.complete`; It's also possible to get it
  working in (:ref:`your REPL (IPython, etc.) <repl-completion>`)
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
- Can infer function arguments from PEP0484-style :ref:`type hints <type-hinting>`,
  sphinx, epydoc and basic numpydoc docstrings
- Understands stub files


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
- some descriptors: property / staticmethod / classmethod
- some magic methods: ``__call__``, ``__iter__``, ``__next__``, ``__get__``,
  ``__getitem__``, ``__init__``
- ``list.append()``, ``set.add()``, ``list.extend()``, etc.
- (nested) list comprehensions / ternary expressions
- relative imports
- ``getattr()`` / ``__getattr__`` / ``__getattribute__``
- function annotations
- class decorators (py3k feature, are being ignored too, until I find a use
  case, that doesn't work with |jedi|)
- simple/usual ``sys.path`` modifications
- ``isinstance`` checks for if/while/assert
- namespace packages (includes ``pkgutil``, ``pkg_resources`` and PEP420 namespaces)
- Django / Flask / Buildout support
- Understands Pytest fixtures


Not Supported
-------------

Things that will probably never be implemented:

- Arbitrary metaclasses (how could an auto-completion ever support this), some
  of them like enums and dataclasses are reimplemented in Jedi to make them
  work. Most of the time stubs are good enough to get type inference working,
  even when metaclasses are involved.
- ``setattr()``, ``__import__()``
- Writing to some dicts: ``globals()``, ``locals()``, ``object.__dict__``
- Manipulations of instances outside the instance variables without using
  methods

Caveats
-------

**Slow Performance**

Importing ``numpy`` can be quite slow sometimes, as well as loading the
builtins the first time. If you want to speed things up, you could preload
libriaries in |jedi|, with :func:`.preload_module`. However, once loaded, this
should not be a problem anymore.  The same is true for huge modules like
``PySide``, ``wx``, ``tensorflow``, ``pandas``, etc.

**Security**

Security is an important issue for |jedi|. Therefore no Python code is
executed.  As long as you write pure Python, everything is inferred
statically. Only if you enable ``load_unsafe_extensions=True`` for your
:class:`.Project` and you use builtin modules (``c_builtin``) Jedi will execute
those modules.
If you don't trust a code base, please do not enable that option. It might lead
to arbitrary code execution.

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
