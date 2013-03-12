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

Basically ``run.py`` searches the ``completion`` directory for files with lines
starting with the symbol above. There is also support for third party
libraries. In a normal test run (``./run.py``) they are not being executed, you
have to provide a ``--thirdparty`` option.

Now it's much more important, that you know how test only one file (``./run.py
classes``, where ``classes`` is the name of the file to test) or even one test
(``./run.py classes 90``, which would just execute the test on line 90).

If you want to debug a test, just use the --debug option.

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
import sys
import re

from . import base  # required to setup import path
import jedi
from jedi._compatibility import unicode, StringIO, reduce, is_py25


sys.path.pop(0)  # pop again, because it might affect the completion


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


def collect_dir_tests(base_dir, test_files, thirdparty=False):
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
