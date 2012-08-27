#!/usr/bin/env python
import os
import sys
import re
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
sys.path.append('.')

from _compatibility import unicode, BytesIO, reduce

import functions
import debug
debug.ignored_modules = ['parsing', 'builtin']


def run_completion_test(correct, source, line_nr, line, path):
    """
    Runs tests for completions.
    Return if the test was a fail or not, with 1 for fail and 0 for success.
    """
    # lines start with 1 and column is just the last (makes no
    # difference for testing)
    try:
        completions = functions.complete(source, line_nr, len(line), path)
        #import cProfile as profile
        #profile.run('functions.complete("""%s""", %i, %i, "%s")'
        #                            % (source, line_nr, len(line), path))
    except Exception:
        print('test @%s: %s' % (line_nr - 1, line))
        print(traceback.format_exc())
        return 1
    else:
        # TODO remove set! duplicates should not be normal
        comp_str = str(sorted(set([str(c) for c in completions])))
        if comp_str != correct:
            print('Solution @%s not right, received %s, wanted %s'\
                        % (line_nr - 1, comp_str, correct))
            return 1
    return 0


def run_definition_test(correct, source, line_nr, line, correct_start, path):
    """
    Runs tests for definitions.
    Return if the test was a fail or not, with 1 for fail and 0 for success.
    """
    def defs(line_nr, indent):
        return set(functions.get_definitions(source, line_nr, indent, path))
    try:
        result = defs(line_nr, len(line))
    except Exception:
        print('test @%s: %s' % (line_nr - 1, line))
        print(traceback.format_exc())
        return 1
    else:
        should_be = set()
        for index in re.finditer('(?: +|$)', correct):
            if correct == ' ':
                continue
            # -1 for the comment, +3 because of the comment start `#? `
            start = index.start() + 3
            try:
                should_be |= defs(line_nr - 1, start + correct_start)
            except Exception:
                print('could not resolve %s indent %s' % (line_nr - 1, start))
                print(traceback.format_exc())
                return 1
        # because the objects have different ids, `repr` it, then compare it.
        should_str = sorted(str(r) for r in should_be)
        is_str = sorted(set(str(r) for r in result))
        if is_str != should_str:
            print('Solution @%s not right, received %s, wanted %s' \
                        % (line_nr - 1, is_str, should_str))
            return 1
    return 0


def run_goto_test(correct, source, line_nr, line, path):
    """
    Runs tests for gotos.
    Tests look like this:
    >>> abc = 1
    >>> #! ['abc=1']
    >>> abc

    Additionally it is possible to add a number which describes to position of
    the test (otherwise it's just end of line.
    >>> #! 2 ['abc=1']
    >>> abc

    For the tests the important things in the end are the positions.

    Return if the test was a fail or not, with 1 for fail and 0 for success.
    """
    r = re.match('^(\d+)\s*(.*)$', correct)
    if r:
        index = int(r.group(1))
        correct = r.group(2)
    else:
        index = len(line)
    try:
        result = functions.goto(source, line_nr, index, path)
    except Exception:
        print('test @%s: %s' % (line_nr - 1, line))
        print(traceback.format_exc())
        return 1
    else:
        comp_str = str(sorted(r.description for r in result))
        if comp_str != correct:
            print('Solution @%s not right, received %s, wanted %s'\
                        % (line_nr - 1, comp_str, correct))
            return 1
    return 0


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
    correct = None
    for line_nr, line in enumerate(BytesIO(source.encode())):
        line = unicode(line)
        line_nr += 1
        if correct:
            # if a list is wanted, use the completion test, otherwise the
            # get_definition test
            path = completion_test_dir + os.path.sep + f_name
            if test_type == '!':
                fails += run_goto_test(correct, source, line_nr, line, path)
            elif correct.startswith('['):
                fails += run_completion_test(correct, source, line_nr, line,
                                                                        path)
            else:
                fails += run_definition_test(correct, source, line_nr, line,
                                                                start, path)
            correct = None
            tests += 1
        else:
            try:
                r = re.search(r'(?:^|(?<=\s))#([?!])\s*([^\n]+)', line)
                # test_type is ? for completion and ! for goto
                test_type = r.group(1)
                correct = r.group(2)
                start = r.start()
            except AttributeError:
                correct = None
            else:
                # reset the test, if only one specific test is wanted
                if lines_to_execute and line_nr not in lines_to_execute:
                    correct = None
    return tests, fails


def test_dir(completion_test_dir, thirdparty=False):
    global tests_pass
    for f_name in os.listdir(completion_test_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            # for python2.5 certain tests are not being done, because it
            # only has these features partially.
            if sys.hexversion < 0x02060000 \
                    and f_name in ['generators.py', 'types.py']:
                continue

            if thirdparty:
                try:
                    # there is always an underline at the end.
                    # It looks like: completion/thirdparty/pylab_.py
                    __import__(f_name.replace('_.py', ''))
                except ImportError:
                    summary.append('Thirdparty-Library %s not found.' %
                                                                    f_name)
                    continue

            path = os.path.join(completion_test_dir, f_name)
            f = open(path)
            num_tests, fails = run_test(f.read(), f_name, lines_to_execute)

            s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
            if fails:
                tests_pass = False
            print(s)
            summary.append(s)


# Sorry I didn't use argparse here. It's because argparse is not in the 
# stdlib in 2.5.
args = sys.argv[1:]
try:
    i = args.index('--thirdparty')
    thirdparty = True
    args = args[:i] + args[i + 1:]
except ValueError:
    thirdparty = False

try:
    i = args.index('--debug')
    args = args[:i] + args[i + 1:]
except ValueError:
    pass
else:
    functions.set_debug_function(debug.print_to_stdout)

# get test list, that should be executed
test_files = {}
last = None
for arg in args:
    if arg.isdigit():
        if last is None:
            continue
        test_files[last].append(int(arg))
    else:
        test_files[arg] = []
        last = arg

# completion tests:
completion_test_dir = 'test/completion'
summary = []
tests_pass = True

# execute tests
test_dir(completion_test_dir)
if test_files or thirdparty:
    completion_test_dir += '/thirdparty'
    test_dir(completion_test_dir, thirdparty=True)

print('\nSummary:')
for s in summary:
    print(s)


exit_code = 0 if tests_pass else 1
sys.exit(exit_code)
