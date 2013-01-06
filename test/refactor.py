#!/usr/bin/env python
import os
import traceback
import re
import base

from _compatibility import unicode, reduce
import api
import refactoring


def run_test(source, f_name, lines_to_execute):
    """
    This is the completion test for some cases. The tests are not unit test
    like, they are rather integration tests.
    It uses comments to specify a test in the next line. The comment also says,
    which results are expected. The comment always begins with `#?`. The last
    row symbolizes the cursor.

    For example:
    >>> #? ['ab']
    >>> ab = 3; a

    >>> #? int()
    >>> ab = 3; ab
    """
    fails = 0
    tests = 0
    s = unicode(source)
    # parse the refactor format
    r = r'^# --- ?([^\n]*)\n((?:(?!\n# \+\+\+).)*)' \
        r'\n# \+\+\+((?:(?!\n# \+\+\+).)*)'
    for match in re.finditer(r, s, re.DOTALL | re.MULTILINE):
        name = match.group(1).strip()
        first = match.group(2).strip()
        second = match.group(3).strip()

        # get the line with the position of the operation
        p = re.match(r'((?:(?!#\?).)*)#\? (\d*) ([^\n]*)', first, re.DOTALL)
        until_pos = p.group(1)
        index = p.group(2)
        new_name = p.group(3)
        line_nr = until_pos.count('\n')

        path = refactoring_test_dir + os.path.sep + f_name
        try:
            script = api.Script(source, line_nr, index, path)
            refactor_func = getattr(refactoring, f_name.replace('.py', ''))
            args = (script, new_name) if new_name else (script,)
            refactor_object = refactor_func(*args)
            print refactor_object.new_files
            if second != refactor_object.new_files:
                print('test @%s: not the same result, %s' % (line_nr - 1, name))
        except Exception:
            print(traceback.format_exc())
            print('test @%s: %s' % (line_nr - 1, name))
            fails += 1
        tests += 1
    return tests, fails


def test_dir(refactoring_test_dir):
    for f_name in os.listdir(refactoring_test_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            path = os.path.join(refactoring_test_dir, f_name)
            with open(path) as f:
                num_tests, fails = run_test(f.read(), f_name, lines_to_execute)

            base.test_sum += num_tests
            s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
            base.tests_fail += fails
            print(s)
            base.summary.append(s)


refactoring_test_dir = '../test/refactor/'
test_files = base.get_test_list()
test_dir(refactoring_test_dir)
