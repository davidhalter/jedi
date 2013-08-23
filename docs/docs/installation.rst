.. include:: ../global.rst

Installation and Configuration
==============================

You can either include |jedi| as a submodule in your text editor plugin (like
jedi-vim_ does by default), or you can install it systemwide.

.. note:: This just installs the |jedi| library, not the :ref:`editor plugins
    <editor-plugins>`. For information about how to make it work with your
    editor, refer to the corresponding documentation.


The preferred way
-----------------

On any system you can install |jedi| directly from the Python package index
using pip::

    sudo pip install jedi

If you want to install the current development version (master branch)::

    sudo pip install -e git://github.com/davidhalter/jedi.git#egg=jedi


System-wide installation via a package manager
----------------------------------------------

Arch Linux
~~~~~~~~~~

You can install |jedi| directly from official AUR packages:

- `python-jedi <https://aur.archlinux.org/packages/python-jedi/>`__ (Python 3)
- `python2-jedi <https://aur.archlinux.org/packages/python2-jedi/>`__ (Python 2)

The specified Python version just refers to the *runtime environment* for
|jedi|. Use the Python 2 version if you're running vim (or whatever editor you
use) under Python 2. Otherwise, use the Python 3 version. But whatever version
you choose, both are able to complete both Python 2 and 3 *code*.

(There is also a packaged version of the vim plugin available: `vim-jedi at AUR
<https://aur.archlinux.org/packages/vim-jedi/>`__.)

Debian
~~~~~~

Debian packages are available in the `unstable repository
<http://packages.debian.org/search?keywords=python%20jedi>`__.

Others
~~~~~~

We are in the discussion of adding |jedi| to the Fedora repositories.


Manual installation from a downloaded package
---------------------------------------------

If you prefer not to use an automated package installer, you can `download
<https://github.com/davidhalter/jedi/archive/master.zip>`__ a current copy of
|jedi| and install it manually.

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
