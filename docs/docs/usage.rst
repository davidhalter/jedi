.. include:: ../global.rst

End User Usage
==============

If you are a not an IDE Developer, the odds are that you just want to use
|jedi| as a browser plugin or in the shell. Yes that's :ref:`also possible
<repl-completion>`!

|jedi| is relatively young and can be used in a variety of Plugins and
Software. If your Editor/IDE is not among them, recommend |jedi| to your IDE
developers.


.. _editor-plugins:

Editor Plugins
--------------

Vim:

- jedi-vim_
- YouCompleteMe_

Emacs:

- Jedi.el_
- elpy_
- company-jedi_

Sublime Text 2/3:

- SublimeJEDI_ (ST2 & ST3)
- anaconda_ (only ST3)

SynWrite:

- SynJedi_

TextMate:

- Textmate_ (Not sure if it's actually working)

Kate:

- Kate_ version 4.13+ supports it natively, you have to enable it, though. [`proof
  <https://projects.kde.org/projects/kde/applications/kate/repository/show?rev=KDE%2F4.13>`_]


.. _other-software:

Other Software Using Jedi
-------------------------

- wdb_ - Web Debugger


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

.. _jedi-vim: https://github.com/davidhalter/jedi-vim
.. _youcompleteme: http://valloric.github.io/YouCompleteMe/
.. _Jedi.el: https://github.com/tkf/emacs-jedi
.. _elpy: https://github.com/jorgenschaefer/elpy
.. _company-jedi: https://github.com/proofit404/company-jedi
.. _sublimejedi: https://github.com/srusskih/SublimeJEDI
.. _anaconda: https://github.com/DamnWidget/anaconda
.. _SynJedi: http://uvviewsoft.com/synjedi/
.. _wdb: https://github.com/Kozea/wdb
.. _TextMate: https://github.com/lawrenceakka/python-jedi.tmbundle
