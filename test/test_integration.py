import os

import pytest

from . import helpers


def assert_case_equal(case, actual, desired):
    """
    Assert ``actual == desired`` with formatted message.

    This is not needed for typical py.test use case, but as we need
    ``--assert=plain`` (see ../pytest.ini) to workaround some issue
    due to py.test magic, let's format the message by hand.
    """
    assert actual == desired, """
Test %r failed.
actual = %s
desired = %s
""" % (case, actual, desired)


def test_integration(case, monkeypatch, pytestconfig):
    if case.skip is not None:
        pytest.skip(case.skip)
    repo_root = helpers.root_dir
    monkeypatch.chdir(os.path.join(repo_root, 'jedi'))
    case.run(assert_case_equal)


def test_refactor(refactor_case):
    """
    Run refactoring test case.

    :type refactor_case: :class:`.refactor.RefactoringCase`
    """
    if 0:
        # TODO Refactoring is not relevant at the moment, it will be changed
        # significantly in the future, but maybe we can use these tests:
        refactor_case.run()
        assert_case_equal(refactor_case,
                          refactor_case.result, refactor_case.desired)
