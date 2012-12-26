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

TODO
