.. include:: ../global.rst

End User Usage
==============

If you are a not an IDE Developer, than chances are pretty high, that you just
want to use |jedi| as a browser plugin or in the shell. Yes that's :ref:`also
possible <repl-completion>`!

|jedi| is relatively young and can be used in a variety of Plugins and
Software. If your Editor/IDE is not among them, recommend |jedi| to your IDE
developers.


.. _editor-plugins:

Editor Plugins
--------------

Vim:

- `jedi-vim <http://github.com/davidhalter/jedi-vim>`_
- `YouCompleteMe <http://valloric.github.io/YouCompleteMe/>`_

Emacs:

- `Jedi.el <https://github.com/tkf/emacs-jedi>`_

Sublime Text 2/3:

- `SublimeJEDI <https://github.com/srusskih/SublimeJEDI>`_  (ST2 & ST3)
- `anaconda <https://github.com/DamnWidget/anaconda>`_ (only ST3)

SynWrite:

- `SynJedi <http://uvviewsoft.com/synjedi/>`_


.. _other-software:

Other Software Using Jedi
-------------------------

- `wdb <https://github.com/Kozea/wdb>`_


.. _repl-completion:

Tab completion in the Python Shell
----------------------------------

There are two different options how you can use Jedi autocompletion in
your Python interpreter. One with your custom ``$HOME/.pythonrc.py`` file
and one that uses ``PYTHONSTARTUP``.

Using ``PYTHONSTARTUP``
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: jedi.replstartup

Using a custom ``$HOME/.pythonrc.py``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: jedi.utils.setup_readline
