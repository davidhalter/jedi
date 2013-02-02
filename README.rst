########################################
Jedi - an awesome Python auto-completion
########################################

.. image:: https://secure.travis-ci.org/davidhalter/jedi.png?branch=master
    :target: http://travis-ci.org/davidhalter/jedi
    :alt: Travis-CI build status

Jedi is an autocompletion tool for Python that can be used in IDEs/editors.
Jedi works. Jedi is fast. It understands all of the basic Python syntax
elements including many builtin functions.

Additionaly, Jedi suports two different goto functions and has support for
renaming as well as Pydoc support and some other IDE features.

Jedi uses a very simple API to connect with IDE's. There's a reference
implementation as a `VIM-Plugin Implementation
<http://github.com/davidhalter/jedi-vim>`_, which uses Jedi's autocompletion.
I encourage you to use Jedi in your IDEs. I'ts really easy. If there are any
problems (also with licensing), just contact me.

Jedi can be used with the following plugins/software:

- `VIM-Plugin <http://github.com/davidhalter/jedi-vim>`_
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

Get the latest version from `github <http://github.com/davidhalter/jedi>`_
(master branch should always be kind of stable/working).

Docs are available at `https://jedi.readthedocs.org/
<https://jedi.readthedocs.org/>`_. Pull requests with documentation enhancements
and/or fixes are awesome and most welcome.

Jedi uses `semantic versioning <http://semver.org/>`_ starting with version
0.6.0.

Installation
============

See https://jedi.readthedocs.org/en/latest/docs/installation.html

Note: This just installs the Jedi library, not the editor plugins. For
information about how to make it work with your editor, refer to the
corresponding documentation.


Feature Support and Caveats
===========================

See https://jedi.readthedocs.org/en/latest/docs/features.html


A little history
================

The Star Wars Jedi are awesome. My Jedi software tries to imitate a little bit
of the precognition the Jedi have. There is even an awesome `scene
<http://www.youtube.com/watch?v=5BDO3pyavOY>`_ of Monty Python Jedi's :-). 

But actually the name hasn't so much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *Oh, that worries me*

When it's finished, I hope he'll like it :-)

I actually started Jedi, because there were no good solutions available for
VIM. Most auto-completions just didn't work well. The only good solution was
PyCharm. I just like my good old VIM. Rope was never really intended to be an
auto-completion (and also I really hate project folders for my Python scripts).
It's more of a refactoring suite. So I decided to do my own version of a
completion, which would execute non-dangerous code. But I soon realized, that
this wouldn't work. So I built an extremely recursive thing which understands
many of Python's key features.

By the way, I really tried to program it as understandable as possible. But I
think understanding it might need quite some time, because of its recursive
nature.


API for IDEs
============

It's very easy to create an editor plugin that uses Jedi. See
https://jedi.readthedocs.org/en/latest/docs/plugin-api.html for more
information.
