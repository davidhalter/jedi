#!/usr/bin/env python
import os
import sys
import re
import StringIO
import traceback

sys.path.append('../')
import functions

#functions.set_debug_function(functions.debug.print_to_stdout)

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
    for line_nr, line in enumerate(StringIO.StringIO(source)):
        line_nr += 1
        if correct:
            # lines start with 1 and column is just the last (makes no
            # difference for testing)
            try:
                completions = functions.complete(source, line_nr, 999,
                                                    completion_test_dir)
            except Exception:
                print 'test @%s: %s' % (line_nr-1, line)
                print traceback.format_exc()
                fails += 1
            else:
                # TODO remove sorted? completions should be sorted?
                # TODO remove set! duplicates should not be normal
                comp_str = str(sorted(set([str(c) for c in completions])))
                if comp_str != correct:
                    print 'Solution @%s not right, received %s, wanted %s'\
                                % (line_nr - 1, comp_str, correct)
                    #print [(c.name, c.name.parent) for c in completions]
                    fails += 1
            correct = None
            tests += 1
        else:
            try:
                correct = re.search(r'(?:^|\s)#\?\s*([^\n]+)', line).group(1)
            except:
                correct = None
            else:
                # reset the test, if only one specific test is wanted
                if len(sys.argv) > 2 and line_nr != int(sys.argv[2]):
                    correct = None
    return tests, fails

# completion tests:
completion_test_dir = 'completion'
summary = []
tests_pass = True
for f_name in os.listdir(completion_test_dir):
    if len(sys.argv) == 1 or [a for a in sys.argv[1:] if a in f_name]:
        if f_name.endswith(".py"):
            path = os.path.join(completion_test_dir, f_name)
            f = open(path)
            num_tests, fails = completion_test(f.read())
            s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
            if fails:
                tests_pass = False
            print s
            summary.append(s)

print '\nSummary:'
for s in summary:
    print s
exit_code = 0 if tests_pass else 1
sys.exit(exit_code)
