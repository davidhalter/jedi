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

.. autofunction:: run_completion_test

Definition
++++++++++

.. autofunction:: run_definition_test

Goto
++++

.. autofunction:: run_goto_test

Related Names
+++++++++++++

.. autofunction:: run_related_name_test
"""
import os
import sys
import re
import traceback

import base

from jedi._compatibility import unicode, StringIO, reduce, literal_eval, is_py25

import jedi
from jedi import debug


sys.path.pop(0)  # pop again, because it might affect the completion


def run_completion_test(script, correct, line_nr):
    """
    Uses comments to specify a test in the next line. The comment says, which
    results are expected. The comment always begins with `#?`. The last row
    symbolizes the cursor.

    For example::

        #? ['real']
        a = 3; a.rea

    Because it follows ``a.rea`` and a is an ``int``, which has a ``real``
    property.

    Returns 1 for fail and 0 for success.
    """
    completions = script.complete()
    #import cProfile; cProfile.run('script.complete()')

    comp_str = set([c.word for c in completions])
    if comp_str != set(literal_eval(correct)):
        print('Solution @%s not right, received %s, wanted %s'\
                    % (line_nr - 1, comp_str, correct))
        return 1
    return 0


def run_definition_test(script, should_str, line_nr):
    """
    Definition tests use the same symbols like completion tests. This is
    possible because the completion tests are defined with a list::

        #? int()
        ab = 3; ab

    Returns 1 for fail and 0 for success.
    """
    result = script.definition()
    is_str = set(r.desc_with_module for r in result)
    if is_str != should_str:
        print('Solution @%s not right, received %s, wanted %s' \
                    % (line_nr - 1, is_str, should_str))
        return 1
    return 0


def run_goto_test(script, correct, line_nr):
    """
    Tests look like this::

        abc = 1
        #! ['abc=1']
        abc

    Additionally it is possible to add a number which describes to position of
    the test (otherwise it's just end of line)::

        #! 2 ['abc=1']
        abc

    Returns 1 for fail and 0 for success.
    """
    result = script.goto()
    comp_str = str(sorted(str(r.description) for r in result))
    if comp_str != correct:
        print('Solution @%s not right, received %s, wanted %s'\
                    % (line_nr - 1, comp_str, correct))
        return 1
    return 0


def run_related_name_test(script, correct, line_nr):
    """
    Tests look like this::

        abc = 1
        #< abc@1,0 abc@3,0
        abc

    Returns 1 for fail and 0 for success.
    """
    result = script.related_names()
    correct = correct.strip()
    compare = sorted((r.module_name, r.start_pos[0], r.start_pos[1])
                                                            for r in result)
    wanted = []
    if not correct:
        positions = []
    else:
        positions = literal_eval(correct)
    for pos_tup in positions:
        if type(pos_tup[0]) == str:
            # this means that there is a module specified
            wanted.append(pos_tup)
        else:
            wanted.append(('renaming', line_nr + pos_tup[0], pos_tup[1]))

    wanted = sorted(wanted)
    if compare != wanted:
        print('Solution @%s not right, received %s, wanted %s'\
                    % (line_nr - 1, compare, wanted))
        return 1
    return 0


def run_test(source, f_name, lines_to_execute):
    """
    This is the completion test for some cases. The tests are not unit test
    like, they are rather integration tests.
    """
    def definition(correct, correct_start, path):
        def defs(line_nr, indent):
            script = jedi.Script(source, line_nr, indent, path)
            return set(script.definition())

        should_be = set()
        number = 0
        for index in re.finditer('(?: +|$)', correct):
            if correct == ' ':
                continue
            # -1 for the comment, +3 because of the comment start `#? `
            start = index.start()
            if base.print_debug:
                jedi.set_debug_function(None)
            number += 1
            try:
                should_be |= defs(line_nr - 1, start + correct_start)
            except Exception:
                print('could not resolve %s indent %s' % (line_nr - 1, start))
                raise
            if base.print_debug:
                jedi.set_debug_function(debug.print_to_stdout)
        # because the objects have different ids, `repr` it, then compare it.
        should_str = set(r.desc_with_module for r in should_be)
        if len(should_str) < number:
            raise Exception('Solution @%s not right, too few test results: %s'
                                                % (line_nr - 1, should_str))
        return should_str

    fails = 0
    tests = 0
    correct = None
    test_type = None
    start = None
    for line_nr, line in enumerate(StringIO(source)):
        line_nr += 1  # py2.5 doesn't know about the additional enumerate param
        line = unicode(line)
        if correct:
            r = re.match('^(\d+)\s*(.*)$', correct)
            if r:
                index = int(r.group(1))
                correct = r.group(2)
                start += r.regs[2][0]  # second group, start index
            else:
                index = len(line) - 1  # -1 for the \n
            # if a list is wanted, use the completion test, otherwise the
            # definition test
            path = completion_test_dir + os.path.sep + f_name
            try:
                script = jedi.Script(source, line_nr, index, path)
                if test_type == '!':
                    fails += run_goto_test(script, correct, line_nr)
                elif test_type == '<':
                    fails += run_related_name_test(script, correct, line_nr)
                elif correct.startswith('['):
                    fails += run_completion_test(script, correct, line_nr)
                else:
                    should_str = definition(correct, start, path)
                    fails += run_definition_test(script, should_str, line_nr)
            except Exception:
                print(traceback.format_exc())
                print('test @%s: %s' % (line_nr - 1, line))
                fails += 1
            correct = None
            tests += 1
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
                # reset the test, if only one specific test is wanted
                if lines_to_execute and line_nr not in lines_to_execute:
                    correct = None
    return tests, fails


def test_dir(completion_test_dir, thirdparty=False):
    for f_name in os.listdir(completion_test_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        lines_to_execute = reduce(lambda x, y: x + y[1], files_to_execute, [])
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            # for python2.5 certain tests are not being done, because it
            # only has these features partially.
            if is_py25 and f_name in ['generators.py', 'types.py']:
                continue

            if thirdparty:
                lib = f_name.replace('_.py', '')
                try:
                    # there is always an underline at the end.
                    # It looks like: completion/thirdparty/pylab_.py
                    __import__(lib)
                except ImportError:
                    base.summary.append('Thirdparty-Library %s not found.' %
                                                                    f_name)
                    continue

            path = os.path.join(completion_test_dir, f_name)
            f = open(path)
            num_tests, fails = run_test(f.read(), f_name, lines_to_execute)
            global test_sum
            base.test_sum += num_tests

            s = 'run %s tests with %s fails (%s)' % (num_tests, fails, f_name)
            base.tests_fail += fails
            print(s)
            base.summary.append(s)


if __name__ == '__main__':
    try:
        i = sys.argv.index('--thirdparty')
        thirdparty = True
        sys.argv = sys.argv[:i] + sys.argv[i + 1:]
    except ValueError:
        thirdparty = False

    test_files = base.get_test_list()

    # completion tests:
    completion_test_dir = '../test/completion'

    # execute tests
    test_dir(completion_test_dir)
    if test_files or thirdparty:
        completion_test_dir += '/thirdparty'
        test_dir(completion_test_dir, thirdparty=True)

    base.print_summary()
    #from guppy import hpy
    #hpy()
    #print hpy().heap()

    exit_code = 1 if base.tests_fail else 0
    if sys.hexversion < 0x02060000 and base.tests_fail <= 9:
        # Python 2.5 has major incompabillities (e.g. no property.setter),
        # therefore it is not possible to pass all tests.
        exit_code = 0
    sys.exit(exit_code)
