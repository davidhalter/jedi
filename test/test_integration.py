import os
import re

from . import base
from .run import \
    TEST_COMPLETIONS, TEST_DEFINITIONS, TEST_ASSIGNMENTS, TEST_USAGES

import jedi
from jedi._compatibility import literal_eval


def run_completion_test(case):
    (script, correct, line_nr) = (case.script(), case.correct, case.line_nr)
    completions = script.complete()
    #import cProfile; cProfile.run('script.complete()')

    comp_str = set([c.word for c in completions])
    if comp_str != set(literal_eval(correct)):
        raise AssertionError(
            'Solution @%s not right, received %s, wanted %s'\
            % (line_nr - 1, comp_str, correct))


def run_definition_test(case):
    def definition(correct, correct_start, path):
        def defs(line_nr, indent):
            s = jedi.Script(script.source, line_nr, indent, path)
            return set(s.definition())

        should_be = set()
        number = 0
        for index in re.finditer('(?: +|$)', correct):
            if correct == ' ':
                continue
            # -1 for the comment, +3 because of the comment start `#? `
            start = index.start()
            number += 1
            try:
                should_be |= defs(line_nr - 1, start + correct_start)
            except Exception:
                print('could not resolve %s indent %s' % (line_nr - 1, start))
                raise
        # because the objects have different ids, `repr` it, then compare it.
        should_str = set(r.desc_with_module for r in should_be)
        if len(should_str) < number:
            raise Exception('Solution @%s not right, too few test results: %s'
                                                % (line_nr - 1, should_str))
        return should_str

    (correct, line_nr, column, start, line) = \
        (case.correct, case.line_nr, case.column, case.start, case.line)
    script = case.script()
    should_str = definition(correct, start, script.source_path)
    result = script.definition()
    is_str = set(r.desc_with_module for r in result)
    if is_str != should_str:
        raise AssertionError(
            'Solution @%s not right, received %s, wanted %s'
            % (line_nr - 1, is_str, should_str))


def run_goto_test(case):
    (script, correct, line_nr) = (case.script(), case.correct, case.line_nr)
    result = script.goto()
    comp_str = str(sorted(str(r.description) for r in result))
    if comp_str != correct:
        raise AssertionError('Solution @%s not right, received %s, wanted %s'
                             % (line_nr - 1, comp_str, correct))


def run_related_name_test(case):
    (script, correct, line_nr) = (case.script(), case.correct, case.line_nr)
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
        raise AssertionError('Solution @%s not right, received %s, wanted %s'
                             % (line_nr - 1, compare, wanted))


def test_integration(case, monkeypatch, pytestconfig):
    repo_root = base.root_dir
    monkeypatch.chdir(os.path.join(repo_root, 'jedi'))
    testers = {
        TEST_COMPLETIONS: run_completion_test,
        TEST_DEFINITIONS: run_definition_test,
        TEST_ASSIGNMENTS: run_goto_test,
        TEST_USAGES: run_related_name_test,
    }
    base.skip_py25_fails(testers[case.test_type])(case)


def test_refactor(refactor_case):
    """
    Run refactoring test case.

    :type refactor_case: :class:`.refactor.RefactoringCase`
    """
    refactor_case.run()
    result, desired = refactor_case.result, refactor_case.desired
    assert result == desired, "Refactoring test %r fails" % refactor_case
