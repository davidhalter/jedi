The plugin API
==============

.. currentmodule:: jedi

If you want to set up an editor/IDE-plugin with **Jedi**, you first need to
``import jedi``. You then have direct access to the :class:`.Script`,
:class:`.NotFoundError` and :func:`.set_debug_function` objects.


API documentation
-----------------

Main class
~~~~~~~~~~

.. module:: api

.. autoclass:: Script
    :members:

API Classes
~~~~~~~~~~~

.. module:: api_classes

.. autoclass:: Completion
    :members:

.. autoclass:: Definition
    :members:

.. autoclass:: RelatedName
    :members:

Exceptions
~~~~~~~~~~

.. module:: api

.. autoexception:: NotFoundError

Useful functions
~~~~~~~~~~~~~~~~

.. module:: api

.. autofunction:: set_debug_function


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

Definitions:

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
    >>> script.goto()
    [<Definition inception=my_list[2]>]
    >>>
    >>> script.get_definition()
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
