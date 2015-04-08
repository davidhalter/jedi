.. :changelog:

Changelog
---------

0.9.0 (2015-04-10)
++++++++++++++++++

- Integrated the parser of 2to3. This will make refactoring possible. It will
  also be possible to check for error messages (like compiling an AST would give)
  in the future.
- With the new parser, the evaluation also completely changed. It's now simpler
  and more readable.
- Completely rewritten REPL completion.
- Added ``jedi.names``, a command to do static analysis. Thanks to that
  sourcegraph guys for sponsoring this!
- Alpha version of the linter.


0.8.1 (2014-07-23)
+++++++++++++++++++

- Bugfix release, the last release forgot to include files that improve
  autocompletion for builtin libraries. Fixed.

0.8.0 (2014-05-05)
+++++++++++++++++++

- Memory Consumption for compiled modules (e.g. builtins, sys) has been reduced
  drastically. Loading times are down as well (it takes basically as long as an
  import).
- REPL completion is starting to become usable.
- Various small API changes. Generally this release focuses on stability and
  refactoring of internal APIs.
- Introducing operator precedence, which makes calculating correct Array
  indices and ``__getattr__`` strings possible.

0.7.0 (2013-08-09)
++++++++++++++++++

- Switched from LGPL to MIT license.
- Added an Interpreter class to the API to make autocompletion in REPL
  possible.
- Added autocompletion support for namespace packages.
- Add sith.py, a new random testing method.

0.6.0 (2013-05-14)
++++++++++++++++++

- Much faster parser with builtin part caching.
- A test suite, thanks @tkf.

0.5 versions (2012)
+++++++++++++++++++

- Initial development.
