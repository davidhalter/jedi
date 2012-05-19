#!/usr/bin/env python
import os
import sys
import re
from io import BytesIO
import traceback

os.chdir('../')
sys.path.append('.')
import functions
from _compatibility import unicode

#functions.set_debug_function(functions.debug.print_to_stdout)

def run_completion_test(correct, source, line_nr, line):
    """
    Runs tests for completions.
    Return if the test was a fail or not, with 1 for fail and 0 for success.
    """
    # lines start with 1 and column is just the last (makes no
    # difference for testing)
    try:
        completions = functions.complete(source, line_nr, 999,
                                            completion_test_dir)
    except Exception:
        print('test @%s: %s' % (line_nr-1, line))
        print(traceback.format_exc())
        return 1
    else:
        # TODO remove sorted? completions should be sorted?
        # TODO remove set! duplicates should not be normal
        comp_str = str(sorted(set([str(c) for c in completions])))
        if comp_str != correct:
            print('Solution @%s not right, received %s, wanted %s'\
                        % (line_nr - 1, comp_str, correct))
            return 1
    return 0


def run_definition_test(correct, source, line_nr, line):
    """
    Runs tests for definitions.
    Return if the test was a fail or not, with 1 for fail and 0 for success.
    """
    def defs(line_nr, indent):
        return set(functions.get_definitions(source, line_nr, indent,
                                            completion_test_dir))
    try:
        result = defs(line_nr, 999)
    except Exception:
        print('test @%s: %s' % (line_nr-1, line))
        print(traceback.format_exc())
        return 1
    else:
        should_be = set()
        for index in re.finditer('(?: +|$)', correct):
            # -1 for the comment, +3 because of the comment start `#? `
            should_be |= defs(line_nr-1, index.start() + 3)
        # because the objects have different ids, `repr` it, then compare it.
        should_str = sorted(str(r) for r in should_be)
        is_str = sorted(str(r) for r in result)
        if is_str != should_str:
            print('Solution @%s not right, received %s, wanted %s' \
                        % (line_nr - 1, is_str, should_str))
            return 1
    return 0


def completion_test(source):
    """
    This is the completion test for some cases. The tests are not unit test
    like, they are rather integration tests.
    It uses comments to specify a test in the next line. The comment also says,
    which results are expected. The comment always begins with `#?`. The last
    row symbolizes the cursor.

    For example:
    #? ['ab']
    ab = 3; a
    """
    fails = 0
    tests = 0
    correct = None
    for line_nr, line in enumerate(BytesIO(source.encode())):
        line = unicode(line)
        line_nr += 1
        if correct:
            # if a list is wanted, use the completion test, otherwise the
            # get_definition test
            if correct.startswith('['):
                fails += run_completion_test(correct, source, line_nr, line)
            else:
                fails += run_definition_test(correct, source, line_nr, line)

            correct = None
            tests += 1
        else:
            try:
                correct = re.search(r'(?:^|\s)#\?\s*([^\n]+)', line).group(1)
            except AttributeError:
                correct = None
            else:
                # reset the test, if only one specific test is wanted
                if len(sys.argv) > 2 and line_nr != int(sys.argv[2]):
                    correct = None
                    import debug
                    debug.debug_function = \
                                functions.debug.print_to_stdout
                    debug.ignored_modules = ['parsing', 'builtin']
    return tests, fails

# completion tests:
completion_test_dir = 'test/completion'
summary = []
for f_name in os.listdir(completion_test_dir):
    if len(sys.argv) == 1 or [a for a in sys.argv[1:] if a in f_name]:
        if f_name.endswith(".py"):
            path = os.path.join(completion_test_dir, f_name)
            f = open(path)
            num_tests, fails = completion_test(f.read())
            s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
            print(s)
            summary.append(s)

print('\nSummary:')
for s in summary:
    print(s)
