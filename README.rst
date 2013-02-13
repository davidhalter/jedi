########################################
Sith - an awesome Python auto-completion
########################################

.. image:: https://secure.travis-ci.org/davidhalter/sith.png?branch=master
    :target: http://travis-ci.org/davidhalter/sith
    :alt: Travis-CI build status

Sith is an autocompletion tool for Python. It works. With and without syntax
errors. Sometimes it sucks, but that's normal in dynamic languages. But it
sucks less than other tools. It understands almost all of the basic Python
syntax elements including many builtins.

Sith suports two different goto functions and has support for renaming.
Probably it will also have some support for refactoring in the future.

Sith uses a very simple interface to connect with IDE's. As an reference, there
is a VIM implementation, which uses Sith's autocompletion. However, I encourage
you to use Sith in your IDEs. Start writing plugins! If there are problems with
licensing, just contact me.

At the moment Sith can be used as a 
`VIM-Plugin <http://github.com/davidhalter/sith-vim>`_. So, if you want to test
Sith for now, you'll have to use VIM. But there are new plugins emerging:

- `Emacs-Plugin <https://github.com/tkf/emacs-sith>`_
- `Sublime-Plugin <https://github.com/svaiter/SublimeJEDI>`_ **Under construction**
- `wdb (web debugger) <https://github.com/Kozea/wdb>`_

Here are some pictures:

.. image:: https://github.com/davidhalter/sith/raw/master/docs/_screenshots/screenshot_complete.png

Completion for almost anything (Ctrl+Space).

.. image:: https://github.com/davidhalter/sith/raw/master/docs/_screenshots/screenshot_function.png

Display of function/class bodies, docstrings.

.. image:: https://github.com/davidhalter/sith/raw/master/docs/_screenshots/screenshot_pydoc.png

Pydoc support (with highlighting, Shift+k).

There is also support for goto and renaming.

Get the latest version from `github <http://github.com/davidhalter/sith>`_
(master branch should always be kind of stable/working).

Docs are available at `https://sith.readthedocs.org/
<https://sith.readthedocs.org/>`_. Pull requests with documentation enhancements
and/or fixes are awesome and most welcome.

Sith uses `semantic versioning <http://semver.org/>`_ starting with version
0.6.0.

Installation
============

See https://sith.readthedocs.org/en/latest/docs/installation.html

Note: This just installs the Sith library, not the editor plugins. For
information about how to make it work with your editor, refer to the
corresponding documentation.


Feature Support and Caveats
===========================

See https://sith.readthedocs.org/en/latest/docs/features.html


A little history
================

The Star Wars Sith are awesome. My Sith software tries to imitate a little bit
of the precognition the Sith have. There is even an awesome `scene
<http://www.youtube.com/watch?v=5BDO3pyavOY>`_ of Monty Python Sith's :-). 

But actually the name hasn't so much to do with Star Wars. It's part of my
second name.

After I explained Guido van Rossum, how some parts of my auto-completion work,
he said (we drank a beer or two):

    *Oh, that worries me*

When it's finished, I hope he'll like it :-)

I actually started Sith, because there were no good solutions available for
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

It's very easy to create an editor plugin that uses Sith. See
https://sith.readthedocs.org/en/latest/docs/plugin-api.html for more
information.
