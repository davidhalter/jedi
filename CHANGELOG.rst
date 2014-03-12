.. :changelog:

Changelog
---------

+0.8.0 (2013-04-01)
+++++++++++++++++++

* Memory Consumption for compiled modules (e.g. builtins, sys) has been reduced
    drastically. Loading times are down as well (it takes basically as long as
    an import).
* REPL completion is starting to become usable.
* Various small API changes. Generally this released focuses on stability and
    refactoring of internal APIs.
* Introducing operator precedence, which makes calculating correct Array
    indices and ``__getattr__`` strings possible.

0.7.0 (2013-08-09)
++++++++++++++++++
* switched from LGPL to MIT license
* added an Interpreter class to the API to make autocompletion in REPL possible.
* added autocompletion support for namespace packages
* add sith.py, a new random testing method

0.6.0 (2013-05-14)
++++++++++++++++++

* much faster parser with builtin part caching
* a test suite, thanks @tkf

0.5 versions (2012)
+++++++++++++++++++

* Initial development
