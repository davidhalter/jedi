#!/usr/bin/env python
"""
|jedi| is mostly being tested by what I would call "Blackbox Tests". These
tests are just testing the interface and do input/output testing. This makes a
lot of sense for |jedi|. Jedi supports so many different code structures, that
it is just stupid to write 200'000 unittests in the manner of
``regression.py``. Also, it is impossible to do doctests/unittests on most of
the internal data structures. That's why |jedi| uses mostly these kind of
tests.

There are different kind of tests:

- complete / definitions ``#?``
- goto: ``#!``
- related names: ``#<``

How to run tests?
+++++++++++++++++

Jedi uses pytest_ to run unit and integration tests.  To run tests,
simply run ``py.test``.  You can also use tox_ to run tests for
multiple Python versions.

.. _pytest: http://pytest.org
.. _tox: http://testrun.org/tox

Integration test cases are located in ``test/completion`` directory
and each test cases are indicated by the comment ``#?`` (complete /
definitions), ``#!`` (assignments) and ``#<`` (usages).  There is also
support for third party libraries. In a normal test run they are not
being executed, you have to provide a ``--thirdparty`` option.

In addition to standard `-k` and `-m` options in py.test, you can use
`-T` (`--test-files`) option to specify integration test cases to run.
It takes the format of ``FILE_NAME[:LINE[,LINE[,...]]]`` where
``FILE_NAME`` is a file in ``test/completion`` and ``LINE`` is a line
number of the test comment.  Here is some recipes:

Run tests only in ``basic.py`` and ``imports.py``::

    py.test test/test_integration.py -T basic.py -T imports.py

Run test at line 4, 6, and 8 in ``basic.py``::

    py.test test/test_integration.py -T basic.py:4,6,8

See ``py.test --help`` for more information.

If you want to debug a test, just use the --pdb option.

Auto-Completion
+++++++++++++++

Uses comments to specify a test in the next line. The comment says, which
results are expected. The comment always begins with `#?`. The last row
symbolizes the cursor.

For example::

    #? ['real']
    a = 3; a.rea

Because it follows ``a.rea`` and a is an ``int``, which has a ``real``
property.

Definition
++++++++++

Definition tests use the same symbols like completion tests. This is
possible because the completion tests are defined with a list::

    #? int()
    ab = 3; ab

Goto
++++

Tests look like this::

    abc = 1
    #! ['abc=1']
    abc

Additionally it is possible to add a number which describes to position of
the test (otherwise it's just end of line)::

    #! 2 ['abc=1']
    abc

Related Names
+++++++++++++

Tests look like this::

    abc = 1
    #< abc@1,0 abc@3,0
    abc
"""
import os
import re

import jedi
from jedi._compatibility import unicode, StringIO, reduce, is_py25


TEST_COMPLETIONS = 0
TEST_DEFINITIONS = 1
TEST_ASSIGNMENTS = 2
TEST_USAGES = 3


class IntegrationTestCase(object):

    def __init__(self, test_type, correct, line_nr, column, start, line,
                 path=None):
        self.test_type = test_type
        self.correct = correct
        self.line_nr = line_nr
        self.column = column
        self.start = start
        self.line = line
        self.path = path

    def __repr__(self):
        name = os.path.basename(self.path) if self.path else None
        return '<%s: %s:%s:%s>' % (self.__class__.__name__,
                                   name, self.line_nr - 1, self.line.rstrip())

    def script(self):
        return jedi.Script(self.source, self.line_nr, self.column, self.path)


def collect_file_tests(lines, lines_to_execute):
    makecase = lambda t: IntegrationTestCase(t, correct, line_nr, column,
                                             start, line)
    start = None
    correct = None
    test_type = None
    for line_nr, line in enumerate(lines):
        line_nr += 1  # py2.5 doesn't know about the additional enumerate param
        line = unicode(line)
        if correct:
            r = re.match('^(\d+)\s*(.*)$', correct)
            if r:
                column = int(r.group(1))
                correct = r.group(2)
                start += r.regs[2][0]  # second group, start index
            else:
                column = len(line) - 1  # -1 for the \n
            if test_type == '!':
                yield makecase(TEST_ASSIGNMENTS)
            elif test_type == '<':
                yield makecase(TEST_USAGES)
            elif correct.startswith('['):
                yield makecase(TEST_COMPLETIONS)
            else:
                yield makecase(TEST_DEFINITIONS)
            correct = None
        else:
            try:
                r = re.search(r'(?:^|(?<=\s))#([?!<])\s*([^\n]+)', line)
                # test_type is ? for completion and ! for goto
                test_type = r.group(1)
                correct = r.group(2)
                start = r.start()
            except AttributeError:
                correct = None
            else:
                # skip the test, if this is not specified test
                if lines_to_execute and line_nr not in lines_to_execute:
                    correct = None


def collect_dir_tests(base_dir, test_files):
    for f_name in os.listdir(base_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            # for python2.5 certain tests are not being done, because it
            # only has these features partially.
            if is_py25 and f_name in ['generators.py', 'types.py']:
                continue
            path = os.path.join(base_dir, f_name)
            source = open(path).read()
            for case in collect_file_tests(StringIO(source),
                                           lines_to_execute):
                case.path = path
                case.source = source
                yield case
