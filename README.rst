###################################################
Jedi - an awesome autocompletion library for Python
###################################################

.. image:: https://secure.travis-ci.org/davidhalter/jedi.png?branch=master
    :target: http://travis-ci.org/davidhalter/jedi
    :alt: Travis-CI build status

.. image:: https://coveralls.io/repos/davidhalter/jedi/badge.png?branch=master
    :target: https://coveralls.io/r/davidhalter/jedi
    :alt: Coverage Status


Jedi is an autocompletion tool for Python that can be used in IDEs/editors.
Jedi works. Jedi is fast. It understands all of the basic Python syntax
elements including many builtin functions.

Additionaly, Jedi suports two different goto functions and has support for
renaming as well as Pydoc support and some other IDE features.

Jedi uses a very simple API to connect with IDE's. There's a reference
implementation as a `VIM-Plugin <https://github.com/davidhalter/jedi-vim>`_,
which uses Jedi's autocompletion.  I encourage you to use Jedi in your IDEs.
It's really easy. If there are any problems (also with licensing), just contact
me.

Jedi can be used with the following plugins/software:

- `VIM-Plugin <https://github.com/davidhalter/jedi-vim>`_
- `Emacs-Plugin <https://github.com/tkf/emacs-jedi>`_
- `Sublime-Plugin <https://github.com/svaiter/SublimeJEDI>`_
- `wdb (web debugger) <https://github.com/Kozea/wdb>`_


Here are some pictures:

.. image:: https://github.com/davidhalter/jedi/raw/master/docs/_screenshots/screenshot_complete.png

Completion for almost anything (Ctrl+Space).

.. image:: https://github.com/davidhalter/jedi/raw/master/docs/_screenshots/screenshot_function.png

Display of function/class bodies, docstrings.

.. image:: https://github.com/davidhalter/jedi/raw/master/docs/_screenshots/screenshot_pydoc.png

Pydoc support (with highlighting, Shift+k).

There is also support for goto and renaming.

Get the latest version from `github <https://github.com/davidhalter/jedi>`_
(master branch should always be kind of stable/working).

Docs are available at `https://jedi.readthedocs.org/
<https://jedi.readthedocs.org/>`_. Pull requests with documentation
enhancements and/or fixes are awesome and most welcome. Jedi uses `semantic
versioning <http://semver.org/>`_.


Installation
============

    pip install jedi

Note: This just installs the Jedi library, not the editor plugins. For
information about how to make it work with your editor, refer to the
corresponding documentation.

You don't want to use ``pip``? Please refer to the `manual
<https://jedi.readthedocs.org/en/latest/docs/installation.html>`_.


Feature Support and Caveats
===========================

Jedi really understands your Python code. For a comprehensive list what Jedi
can do, see: `Features
<https://jedi.readthedocs.org/en/latest/docs/features.html>`_. A list of
caveats can be found on the same page.

You can run Jedi on cPython 2.6, 2.7, 3.2 or 3.3, but it should also
understand/parse code older than those versions.

Tips on how to use Jedi efficiently can be found `here
<https://jedi.readthedocs.org/en/latest/docs/recipes.html>`_.


API for IDEs
============

It's very easy to create an editor plugin that uses Jedi. See `Plugin API
<https://jedi.readthedocs.org/en/latest/docs/plugin-api.html>`_ for more
information.


Development
===========

There's a pretty good and extensive `development documentation
<https://jedi.readthedocs.org/en/latest/docs/development.html>`_.


Testing
=======

The test suite depends on ``tox`` and ``pytest``::

    pip install tox pytest

To run the tests for all supported Python versions::

    tox

If you want to test only a specific Python version (e.g. Python 2.7), it's as
easy as ::

    tox -e py27

Tests are also run automatically on `Travis CI
<https://travis-ci.org/davidhalter/jedi/>`_.

For more detailed information visit the `testing documentation
<https://jedi.readthedocs.org/en/latest/docs/testing.html>`_
