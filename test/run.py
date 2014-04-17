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

- completions / goto_definitions ``#?``
- goto_assignments: ``#!``
- usages: ``#<``

How to run tests?
+++++++++++++++++

Jedi uses pytest_ to run unit and integration tests.  To run tests,
simply run ``py.test``.  You can also use tox_ to run tests for
multiple Python versions.

.. _pytest: http://pytest.org
.. _tox: http://testrun.org/tox

Integration test cases are located in ``test/completion`` directory
and each test cases are indicated by the comment ``#?`` (completions /
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

If you want to debug a test, just use the ``--pdb`` option.

Alternate Test Runner
+++++++++++++++++++++

If you don't like the output of ``py.test``, there's an alternate test runner
that you can start by running ``./run.py``. The above example could be run by::

    ./run.py basic 4 6 8

The advantage of this runner is simplicity and more customized error reports.
Using both runners will help you to have a quicker overview of what's
happening.


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

Goto Definitions
++++++++++++++++

Definition tests use the same symbols like completion tests. This is
possible because the completion tests are defined with a list::

    #? int()
    ab = 3; ab

Goto Assignments
++++++++++++++++

Tests look like this::

    abc = 1
    #! ['abc=1']
    abc

Additionally it is possible to add a number which describes to position of
the test (otherwise it's just end of line)::

    #! 2 ['abc=1']
    abc

Usages
++++++

Tests look like this::

    abc = 1
    #< abc@1,0 abc@3,0
    abc
"""
import os
import re
from ast import literal_eval
from io import StringIO
from functools import reduce

import jedi
from jedi._compatibility import unicode, is_py3


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
        self.skip = None

    @property
    def module_name(self):
        return re.sub('.*/|\.py$', '', self.path)

    @property
    def line_nr_test(self):
        """The test is always defined on the line before."""
        return self.line_nr - 1

    def __repr__(self):
        return '<%s: %s:%s:%s>' % (self.__class__.__name__, self.module_name,
                                   self.line_nr_test, self.line.rstrip())

    def script(self):
        return jedi.Script(self.source, self.line_nr, self.column, self.path)

    def run(self, compare_cb):
        testers = {
            TEST_COMPLETIONS: self.run_completion,
            TEST_DEFINITIONS: self.run_goto_definitions,
            TEST_ASSIGNMENTS: self.run_goto_assignments,
            TEST_USAGES: self.run_usages,
        }
        return testers[self.test_type](compare_cb)

    def run_completion(self, compare_cb):
        completions = self.script().completions()
        #import cProfile; cProfile.run('script.completions()')

        comp_str = set([c.name for c in completions])
        return compare_cb(self, comp_str, set(literal_eval(self.correct)))

    def run_goto_definitions(self, compare_cb):
        def definition(correct, correct_start, path):
            def defs(line_nr, indent):
                s = jedi.Script(self.source, line_nr, indent, path)
                return set(s.goto_definitions())

            should_be = set()
            number = 0
            for index in re.finditer('(?: +|$)', correct):
                if correct == ' ':
                    continue
                # -1 for the comment, +3 because of the comment start `#? `
                start = index.start()
                number += 1
                try:
                    should_be |= defs(self.line_nr - 1, start + correct_start)
                except Exception:
                    print('could not resolve %s indent %s'
                          % (self.line_nr - 1, start))
                    raise
            # because the objects have different ids, `repr`, then compare.
            should_str = set(r.desc_with_module for r in should_be)
            if len(should_str) < number:
                raise Exception('Solution @%s not right, '
                   'too few test results: %s' % (self.line_nr - 1, should_str))
            return should_str

        script = self.script()
        should_str = definition(self.correct, self.start, script.path)
        result = script.goto_definitions()
        is_str = set(r.desc_with_module for r in result)
        return compare_cb(self, is_str, should_str)

    def run_goto_assignments(self, compare_cb):
        result = self.script().goto_assignments()
        comp_str = str(sorted(str(r.description) for r in result))
        return compare_cb(self, comp_str, self.correct)

    def run_usages(self, compare_cb):
        result = self.script().usages()
        self.correct = self.correct.strip()
        compare = sorted((r.module_name, r.line, r.column) for r in result)
        wanted = []
        if not self.correct:
            positions = []
        else:
            positions = literal_eval(self.correct)
        for pos_tup in positions:
            if type(pos_tup[0]) == str:
                # this means that there is a module specified
                wanted.append(pos_tup)
            else:
                line = pos_tup[0]
                if pos_tup[0] is not None:
                    line += self.line_nr
                wanted.append((self.module_name, line, pos_tup[1]))

        return compare_cb(self, compare, sorted(wanted))


def collect_file_tests(lines, lines_to_execute):
    makecase = lambda t: IntegrationTestCase(t, correct, line_nr, column,
                                             start, line)
    start = None
    correct = None
    test_type = None
    for line_nr, line in enumerate(lines, 1):
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
                # test_type is ? for completion and ! for goto_assignments
                test_type = r.group(1)
                correct = r.group(2)
                start = r.start()
            except AttributeError:
                correct = None
            else:
                # skip the test, if this is not specified test
                if lines_to_execute and line_nr not in lines_to_execute:
                    correct = None


def collect_dir_tests(base_dir, test_files, check_thirdparty=False):
    for f_name in os.listdir(base_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            skip = None
            if check_thirdparty:
                lib = f_name.replace('_.py', '')
                try:
                    # there is always an underline at the end.
                    # It looks like: completion/thirdparty/pylab_.py
                    __import__(lib)
                except ImportError:
                    skip = 'Thirdparty-Library %s not found.' % lib

            path = os.path.join(base_dir, f_name)
            source = open(path).read()
            if not is_py3:
                source = unicode(source, 'UTF-8')
            for case in collect_file_tests(StringIO(source),
                                           lines_to_execute):
                case.path = path
                case.source = source
                if skip:
                    case.skip = skip
                yield case


docoptstr = """
Using run.py to make debugging easier with integration tests.

An alternative testing format, which is much more hacky, but very nice to
work with.

Usage:
    run.py [--pdb] [--debug] [--thirdparty] [<rest>...]
    run.py --help

Options:
    -h --help       Show this screen.
    --pdb           Enable pdb debugging on fail.
    -d, --debug     Enable text output debugging (please install ``colorama``).
    --thirdparty    Also run thirdparty tests (in ``completion/thirdparty``).
"""
if __name__ == '__main__':
    import docopt
    arguments = docopt.docopt(docoptstr)

    import time
    t_start = time.time()
    # Sorry I didn't use argparse here. It's because argparse is not in the
    # stdlib in 2.5.
    import sys

    if arguments['--debug']:
        jedi.set_debug_function()

    # get test list, that should be executed
    test_files = {}
    last = None
    for arg in arguments['<rest>']:
        if arg.isdigit():
            if last is None:
                continue
            test_files[last].append(int(arg))
        else:
            test_files[arg] = []
            last = arg

    # completion tests:
    completion_test_dir = '../test/completion'
    summary = []
    tests_fail = 0

    # execute tests
    cases = list(collect_dir_tests(completion_test_dir, test_files))
    if test_files or arguments['--thirdparty']:
        completion_test_dir += '/thirdparty'
        cases += collect_dir_tests(completion_test_dir, test_files, True)

    def file_change(current, tests, fails):
        if current is not None:
            current = os.path.basename(current)
        print('%s \t\t %s tests and %s fails.' % (current, tests, fails))

    def report(case, actual, desired):
        if actual == desired:
            return 0
        else:
            print("\ttest fail @%d, actual = %s, desired = %s"
                  % (case.line_nr - 1, actual, desired))
            return 1

    import traceback
    current = cases[0].path if cases else None
    count = fails = 0
    for c in cases:
        try:
            if c.run(report):
                tests_fail += 1
                fails += 1
        except Exception:
            traceback.print_exc()
            print("\ttest fail @%d" % (c.line_nr - 1))
            tests_fail += 1
            fails += 1
            if arguments['--pdb']:
                import pdb
                pdb.post_mortem()

        count += 1

        if current != c.path:
            file_change(current, count, fails)
            current = c.path
            count = fails = 0
    file_change(current, count, fails)

    print('\nSummary: (%s fails of %s tests) in %.3fs' % (tests_fail,
                                        len(cases), time.time() - t_start))
    for s in summary:
        print(s)

    exit_code = 1 if tests_fail else 0
    sys.exit(exit_code)
