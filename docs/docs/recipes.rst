.. include:: ../global.rst

Recipes
=======

Here are some tips on how to use |jedi| efficiently.


.. _type-hinting:

Type Hinting
------------

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

        @param node: ProgramNode

        """
        node.| # complete here
