#!/usr/bin/env python
"""
Refactoring tests work a little bit similar to Black Box tests. But the idea is
here to compare two versions of code.
"""
from __future__ import with_statement
import sys
import os
import traceback
import re
import itertools

import base

from jedi._compatibility import reduce
import jedi
from jedi import refactoring


class RefactoringCase(object):

    def __init__(self, name, source, line_nr, index, path, f_name,
                 new_name, start_line_test, desired):
        self.name = name
        self.source = source
        self.line_nr = line_nr
        self.index = index
        self.path = path
        self.f_name = f_name
        self.new_name = new_name
        self.start_line_test = start_line_test
        self.desired = desired

    def run(self):
        (source, line_nr, index, path, f_name, new_name, start_line_test) \
            = (self.source, self.line_nr, self.index, self.path, self.f_name,
               self.new_name, self.start_line_test)
        script = jedi.Script(source, line_nr, index, path)
        refactor_func = getattr(refactoring, f_name.replace('.py', ''))
        args = (script, new_name) if new_name else (script,)
        refactor_object = refactor_func(*args)

        # try to get the right excerpt of the newfile
        f = refactor_object.new_files()[path]
        lines = f.splitlines()[start_line_test:]

        end = start_line_test + len(lines)
        pop_start = None
        for i, l in enumerate(lines):
            if l.startswith('# +++'):
                end = i
                break
            elif '#? ' in l:
                pop_start = i
        lines.pop(pop_start)
        self.result = '\n'.join(lines[:end - 1]).strip()
        return self.result

    def check(self):
        return self.run() == self.desired

    def __repr__(self):
        return '<%s: %s:%s>' % (self.__class__.__name__,
                                self.name, self.line_nr - 1)


def collect_file_tests(source, f_name, lines_to_execute):
    r = r'^# --- ?([^\n]*)\n((?:(?!\n# \+\+\+).)*)' \
        r'\n# \+\+\+((?:(?!\n# ---).)*)'
    for match in re.finditer(r, source, re.DOTALL | re.MULTILINE):
        name = match.group(1).strip()
        first = match.group(2).strip()
        second = match.group(3).strip()
        start_line_test = source[:match.start()].count('\n') + 1

        # get the line with the position of the operation
        p = re.match(r'((?:(?!#\?).)*)#\? (\d*) ?([^\n]*)', first, re.DOTALL)
        if p is None:
            print("Please add a test start.")
            continue
        until = p.group(1)
        index = int(p.group(2))
        new_name = p.group(3)

        line_nr = start_line_test + until.count('\n') + 2
        if lines_to_execute and line_nr - 1 not in lines_to_execute:
            continue

        path = os.path.abspath(refactoring_test_dir + os.path.sep + f_name)
        yield RefactoringCase(name, source, line_nr, index, path, f_name,
                              new_name, start_line_test, second)


def collect_dir_tests(base_dir, test_files):
    for f_name in os.listdir(base_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            path = os.path.join(refactoring_test_dir, f_name)
            with open(path) as f:
                source = f.read()
            for case in collect_file_tests(source, f_name, lines_to_execute):
                yield case


def run_test(cases):
    """
    This is the completion test for some cases. The tests are not unit test
    like, they are rather integration tests.
    It uses comments to specify a test in the next line. The comment also says,
    which results are expected. The comment always begins with `#?`. The last
    row symbolizes the cursor.

    For example::

        #? ['ab']
        ab = 3; a

        #? int()
        ab = 3; ab
    """
    fails = 0
    tests = 0
    for case in cases:
        try:
            if not case.check():
                print(case)
                print('    ' + repr(str(case.result)))
                print('    ' + repr(case.desired))
                fails += 1
        except Exception:
            print(traceback.format_exc())
            print(case)
            fails += 1
        tests += 1
    return tests, fails


def test_dir(refactoring_test_dir):
    for (path, cases) in itertools.groupby(
            collect_dir_tests(refactoring_test_dir, test_files),
            lambda case: case.path):
        num_tests, fails = run_test(cases)

        base.test_sum += num_tests
        f_name = os.path.basename(path)
        s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
        base.tests_fail += fails
        print(s)
        base.summary.append(s)


if __name__ == '__main__':
    refactoring_test_dir = os.path.join(base.test_dir, 'refactor')
    test_files = base.get_test_list()
    test_dir(refactoring_test_dir)

    base.print_summary()

    sys.exit(1 if base.tests_fail else 0)
