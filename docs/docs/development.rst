.. include:: ../global.rst

Jedi Development
================

.. currentmodule:: jedi

.. note:: This documentation is for Jedi developers, who want to improve Jedi
    itself, but have just no idea how Jedi works. If you want to use Jedi for 
    your IDE, look at the `plugin api <plugin-api.html>`_.


This page tries to address the fundamental demand for documentation of the
|jedi| interals. Understanding a dynamic language is a complex task. Especially
because type inference in Python can be a very recursive task. Therefore |jedi|
couldn't get rid of complexity. We know that **simple is better than complex**,
but unfortunately it requires sometimes complex solutions to understand complex
systems.


Core
----

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



Imports and Modules
-------------------

Modules (modules.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: module

Builtin Modules (builtin.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: builtin

Imports (imports.py)
~~~~~~~~~~~~~~~~~~~~

.. automodule:: imports



Caching and Recursions
----------------------

Caching (cache.py)
~~~~~~~~~~~~~~~~~~

.. automodule:: cache

Recursions (recursion.py)
~~~~~~~~~~~~~~~~~~~~~~~~~

TODO need to refactor the recursion stuff out of helpers.py
#.. automodule:: recursion



Extensions
----------

Docstrings (docstrings.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: docstrings

Dynamic Arrays & Function Parameters (dynamic.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: dynamic

Refactoring (docstrings.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: refactoring



Helpers Modules
---------------

There are some helper modules: `common.py`, `helpers.py`, `debug.py`,
`keywords.py`, which I won't describe further. Some functions are inheritely
important and central for Jedi to work, but not important to understand how
Jedi works.

Python 2/3 compatibility (_compatibility.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: _compatibility
