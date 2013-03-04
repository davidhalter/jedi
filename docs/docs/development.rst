.. include:: ../global.rst

Jedi Development
================

.. currentmodule:: jedi

.. note:: This documentation is for Jedi developers who want to improve Jedi
    itself, but have no idea how Jedi works. If you want to use Jedi for 
    your IDE, look at the `plugin api <plugin-api.html>`_.


Introduction
------------

This page tries to address the fundamental demand for documentation of the
|jedi| interals. Understanding a dynamic language is a complex task. Especially
because type inference in Python can be a very recursive task. Therefore |jedi|
couldn't get rid of complexity. I know that **simple is better than complex**,
but unfortunately it sometimes requires complex solutions to understand complex
systems.

Since most of the Jedi internals have been written by me (David Halter), this
introduction will be written mostly by me, because no one else understands to
the same level how Jedi works. Actually this is also the reason for exactly this
part of the documentation. To make multiple people able to edit the Jedi core.

In five chapters I'm trying to describe the internals of |jedi|:

- :ref:`The Jedi Core <core>`
- :ref:`Core Extensions <core-extensions>`
- :ref:`Imports & Modules <imports-modules>`
- :ref:`Caching & Recursions <caching-recursions>`
- :ref:`Helper modules <dev-helpers>`

.. note:: Testing is not documented here, you'll find that
   `right here <testing.html>`_.


.. _core:

The Jedi Core
-------------

The core of Jedi consists of three parts:

- :ref:`Parser <parsing>`
- :ref:`Python code evaluation <evaluate>`
- :ref:`API <dev-api>`

Most people are probably interested in :ref:`code evaluation <evaluate>`,
because that's where all the magic happens. I need to introduce the :ref:`parser
<parsing>` first, because :mod:`evaluate` uses it extensively.

.. _parsing:

Parser (parsing.py)
~~~~~~~~~~~~~~~~~~~

.. automodule:: parsing

Parser Representation (parser_representation.py)
++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: parsing_representation

.. inheritance-diagram::
   SubModule
   Class
   Function
   Lambda
   Flow
   ForFlow
   Import
   Statement
   Param
   Call
   Array
   Name
   ListComprehension
   :parts: 1

.. _evaluate:

Evaluation of python code (evaluate.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: evaluate

Evaluation Representation (evaluate_representation.py)
++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. automodule:: evaluate_representation

.. inheritance-diagram::
   Executable
   Instance
   InstanceElement
   Class
   Function
   Execution
   Generator
   Array
   :parts: 1

.. _dev-api:

API (api.py and api_classes.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The API has been designed to be as easy to use as possible. The API
documentation can be found `here <plugin-api.html>`_. The API itself contains
little code that needs to be mentioned here. Generally I'm trying to be
conservative with the API.  I'd rather not add new API features if they are not
necessary, because it's much harder to deprecate stuff than to add it later.



.. _core-extensions:

Core Extensions
---------------

Core Extensions is a summary of the following topics:

- :ref:`Dynamic Arrays & Function Parameters <dynamic>`
- :ref:`Fast Parser <fast_parser>`
- :ref:`Docstrings <docstrings>`
- :ref:`Refactoring <refactoring>`

These topics are very important to understand what Jedi additionally does, but
they could be removed from Jedi and Jedi would still work. But slower and
without some features.

.. _dynamic:

Dynamic Arrays & Function Parameters (dynamic.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: dynamic


.. _fast_parser:

Fast Parser (fast_parser.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: fast_parser

.. _docstrings:

Docstrings (docstrings.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: docstrings

.. _refactoring:

Refactoring (refactoring.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: refactoring



.. _imports-modules:

Imports & Modules
-------------------


- :ref:`Modules <modules>`
- :ref:`Builtin Modules <builtin>`
- :ref:`Imports <imports>`

.. _modules:

Modules (modules.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: modules

.. _builtin:

Builtin Modules (builtin.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: builtin

.. _imports:

Imports (imports.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: imports



.. _caching-recursions:

Caching & Recursions
----------------------


- :ref:`Caching <cache>`
- :ref:`Recursions <recursion>`

.. _cache:

Caching (cache.py)
~~~~~~~~~~~~~~~~~~

.. automodule:: cache

.. _recursion:

Recursions (recursion.py)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: recursion



.. _dev-helpers:

Helper Modules
---------------

There are some helper modules: `common.py`, `helpers.py`, `debug.py`,
`keywords.py`, which I won't describe further. Some functions are inheritely
important and central for Jedi to work, but not important to understand how
Jedi works.

Python 2/3 compatibility (_compatibility.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: _compatibility
