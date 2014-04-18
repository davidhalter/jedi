.. include:: ../global.rst

The Plugin API
==============

.. currentmodule:: jedi

Note: This documentation is for Plugin developers, who want to improve their
editors/IDE autocompletion 

If you want to use |jedi|, you first need to ``import jedi``.  You then have
direct access to the :class:`.Script`. You can then call the functions
documented here. These functions return :ref:`API classes
<plugin-api-classes>`.


Deprecations
------------

The deprecation process is as follows:

1. A deprecation is announced in the next major/minor release.
2. We wait either at least a year & at least two minor releases until we remove
   the deprecated functionality.


API documentation
-----------------

API Interface
~~~~~~~~~~~~~

.. automodule:: jedi.api
    :members:
    :undoc-members:


Examples
--------

Completions:

.. sourcecode:: python

   >>> import jedi
   >>> source = '''import json; json.l'''
   >>> script = jedi.Script(source, 1, 19, '')
   >>> script
   <jedi.api.Script object at 0x2121b10>
   >>> completions = script.complete()
   >>> completions
   [<Completion: load>, <Completion: loads>]
   >>> completions[1]
   <Completion: loads>
   >>> completions[1].complete
   'oads'
   >>> completions[1].word
   'loads'

Definitions / Goto:

.. sourcecode:: python

    >>> import jedi
    >>> source = '''def my_func():
    ...     print 'called'
    ... 
    ... alias = my_func
    ... my_list = [1, None, alias]
    ... inception = my_list[2]
    ... 
    ... inception()'''
    >>> script = jedi.Script(source, 8, 1, '')
    >>>
    >>> script.goto_assignments()
    [<Definition inception=my_list[2]>]
    >>>
    >>> script.goto_definitions()
    [<Definition def my_func>]

Related names:

.. sourcecode:: python

    >>> import jedi
    >>> source = '''x = 3
    ... if 1 == 2:
    ...     x = 4
    ... else:
    ...     del x'''
    >>> script = jedi.Script(source, 5, 8, '')
    >>> rns = script.related_names()
    >>> rns
    [<RelatedName x@3,4>, <RelatedName x@1,0>]
    >>> rns[0].start_pos
    (3, 4)
    >>> rns[0].is_keyword
    False
    >>> rns[0].text
    'x'
