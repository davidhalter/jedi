import os
import sys
from collections import namedtuple

import pytest

from . import helpers
from jedi.common import indent_block
from jedi import RefactoringError


def assert_case_equal(case, actual, desired):
    """
    Assert ``actual == desired`` with formatted message.

    This is not needed for typical pytest use case, but as we need
    ``--assert=plain`` (see ../pytest.ini) to workaround some issue
    due to pytest magic, let's format the message by hand.
    """
    assert actual == desired, """
Test %r failed.
actual  =
%s
desired =
%s
""" % (case, indent_block(str(actual)), indent_block(str(desired)))


def assert_static_analysis(case, actual, desired):
    """A nicer formatting for static analysis tests."""
    a = set(actual)
    d = set(desired)
    assert actual == desired, """
Test %r failed.
not raised  = %s
unspecified = %s
""" % (case, sorted(d - a), sorted(a - d))


def test_completion(case, monkeypatch, environment, has_django):
    skip_reason = case.get_skip_reason(environment)
    if skip_reason is not None:
        pytest.skip(skip_reason)

    if (not has_django) and case.path.endswith('django.py'):
        pytest.skip('Needs django to be installed to run this test.')

    if case.path.endswith("pytest.py"):
        # to test finding pytest fixtures from external plugins
        # add a stub pytest plugin to the project sys_path...
        pytest_plugin_dir = str(helpers.get_example_dir("pytest_plugin_package"))
        case._project.added_sys_path = [pytest_plugin_dir]

        # ... and mock the entry points to include it
        # see https://docs.pytest.org/en/stable/how-to/writing_plugins.html#setuptools-entry-points
        if sys.version_info >= (3, 8):
            def mock_entry_points(*, group=None):
                import importlib.metadata
                entries = [importlib.metadata.EntryPoint(
                    name=None,
                    value="pytest_plugin.plugin",
                    group="pytest11",
                )]

                if sys.version_info >= (3, 10):
                    assert group == "pytest11"
                    return entries
                else:
                    assert group is None
                    return {"pytest11": entries}

            monkeypatch.setattr("importlib.metadata.entry_points", mock_entry_points)
        else:
            def mock_iter_entry_points(group):
                assert group == "pytest11"
                EntryPoint = namedtuple("EntryPoint", ["module_name"])
                return [EntryPoint("pytest_plugin.plugin")]

            monkeypatch.setattr("pkg_resources.iter_entry_points", mock_iter_entry_points)

    repo_root = helpers.root_dir
    monkeypatch.chdir(os.path.join(repo_root, 'jedi'))
    case.run(assert_case_equal, environment)


def test_static_analysis(static_analysis_case, environment):
    skip_reason = static_analysis_case.get_skip_reason(environment)
    if skip_reason is not None:
        pytest.skip(skip_reason)
    else:
        static_analysis_case.run(assert_static_analysis, environment)


def test_refactor(refactor_case, environment):
    """
    Run refactoring test case.

    :type refactor_case: :class:`.refactor.RefactoringCase`
    """
    desired_result = refactor_case.get_desired_result()
    if refactor_case.type == 'error':
        with pytest.raises(RefactoringError) as e:
            refactor_case.refactor(environment)
        assert e.value.args[0] == desired_result.strip()
    elif refactor_case.type == 'text':
        refactoring = refactor_case.refactor(environment)
        assert not refactoring.get_renames()
        text = ''.join(f.get_new_code() for f in refactoring.get_changed_files().values())
        assert_case_equal(refactor_case, text, desired_result)
    else:
        diff = refactor_case.refactor(environment).get_diff()
        assert_case_equal(refactor_case, diff, desired_result)
