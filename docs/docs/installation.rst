.. include:: ../global.rst

Installation and Configuration
==============================

You can either include |jedi| as a submodule in your text editor plugin (like
jedi-vim_ does by default), or you can install it systemwide.


System-wide installation via a package manager
----------------------------------------------

You can install |jedi| directly from pypi using pip::

    sudo pip install jedi

If you want to install the current development version (master branch)::

    sudo pip install -e git://github.com/davidhalter/jedi.git#egg=jedi

.. note:: This just installs the |jedi| library, not the :ref:`editor plugins
    <editor-plugins>`. For information about how to make it work with your
    editor, refer to the corresponding documentation.


Manual installation from a downloaded package
---------------------------------------------

If you prefer not to use an automated package installer, you can `download
<https://github.com/davidhalter/jedi/archive/master.zip>`__ a current copy of
*Jedi* and install it manually.

To install it, navigate to the directory containing `setup.py` on your console
and type::

    sudo python setup.py install


Inclusion as a submodule
------------------------

If you use an editor plugin like jedi-vim_, you can simply include |jedi| as a
git submodule of the plugin directory. Vim plugin managers like Vundle_ or
Pathogen_ make it very easy to keep submodules up to date.


.. _jedi-vim: https://github.com/davidhalter/jedi-vim
.. _vundle: https://github.com/gmarik/vundle
.. _pathogen: https://github.com/tpope/vim-pathogen
