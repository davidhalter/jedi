.. include:: ../global.rst

Jedi Development
================

.. currentmodule:: jedi

.. note:: This documentation is for Jedi developers, who want to improve Jedi
    itself, but have just no idea how Jedi works. If you want to use Jedi for 
    your IDE, look at the `plugin api <plugin-api.html>`_.


Introduction
------------

This page tries to address the fundamental demand for documentation of the
|jedi| interals. Understanding a dynamic language is a complex task. Especially
because type inference in Python can be a very recursive task. Therefore |jedi|
couldn't get rid of complexity. We know that **simple is better than complex**,
but unfortunately it requires sometimes complex solutions to understand complex
systems.


In five chapters we're trying to describe the internals of |jedi|:

- :ref:`The Jedi Core <dev-core>`
- :ref:`Core Extensions <dev-extensions>`
- :ref:`Imports & Modules <dev-imports-modules>`
- :ref:`Caching & Recursions <dev-caching-recursions>`
- :ref:`Helper modules <dev-helpers>`


.. _dev-core:

The Jedi Core
-------------

The core of Jedi consists of three parts:

- :ref:`API <dev-api>`
- :ref:`Parser <dev-parser>`
- :ref:`Python code evaluation <dev-evaluate>`

.. _dev-api:

API (api.py and api_classes.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API

.. _dev-parsing:

Parser (parsing.py)
~~~~~~~~~~~~~~~~~~~

.. automodule:: parsing

.. _dev-evaluate:

Evaluation of python code (evaluate.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: evaluate



.. _dev-extensions:

Core Extensions
---------------

Core Extensions is a summary of the following topics:

- :ref:`Dynamic Arrays & Function Parameters <dev-dynamic>`
- :ref:`Docstrings <dev-docstrings>`
- :ref:`Refactoring <dev-refactoring>`

These topics are very important to understand what Jedi additionally does, but
they could be removed from Jedi and Jedi would still work. But logically
without refactoring support, docstrings and the understanding of the dynamic
nature of Python.


.. _dev-dynamic:

Dynamic Arrays & Function Parameters (dynamic.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: dynamic

.. _dev-docstrings:

Docstrings (docstrings.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: docstrings

.. _dev-refactoring:

Refactoring (docstrings.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: refactoring


.. _dev-imports-modules:



Imports & Modules
-------------------

Modules (modules.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: modules

Builtin Modules (builtin.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: builtin

Imports (imports.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: imports



.. _dev-caching-recursions:

Caching & Recursions
----------------------

Caching (cache.py)
~~~~~~~~~~~~~~~~~~

.. automodule:: cache

Recursions (recursion.py)
~~~~~~~~~~~~~~~~~~~~~~~~~

TODO need to refactor the recursion stuff out of helpers.py
#.. automodule:: recursion



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
