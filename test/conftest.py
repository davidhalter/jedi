import os
import shutil
import re
import tempfile

import pytest

from . import helpers
from . import run
from . import refactor
import jedi
from jedi.evaluate.analysis import Warning


def pytest_addoption(parser):
    parser.addoption(
        "--integration-case-dir",
        default=os.path.join(helpers.test_dir, 'completion'),
        help="Directory in which integration test case files locate.")
    parser.addoption(
        "--refactor-case-dir",
        default=os.path.join(helpers.test_dir, 'refactor'),
        help="Directory in which refactoring test case files locate.")
    parser.addoption(
        "--test-files", "-T", default=[], action='append',
        help=(
            "Specify test files using FILE_NAME[:LINE[,LINE[,...]]]. "
            "For example: -T generators.py:10,13,19. "
            "Note that you can use -m to specify the test case by id."))
    parser.addoption(
        "--thirdparty", action='store_true',
        help="Include integration tests that requires third party modules.")


def parse_test_files_option(opt):
    """
    Parse option passed to --test-files into a key-value pair.

    >>> parse_test_files_option('generators.py:10,13,19')
    ('generators.py', [10, 13, 19])
    """
    opt = str(opt)
    if ':' in opt:
        (f_name, rest) = opt.split(':', 1)
        return (f_name, list(map(int, rest.split(','))))
    else:
        return (opt, [])


def pytest_generate_tests(metafunc):
    """
    :type metafunc: _pytest.python.Metafunc
    """
    test_files = dict(map(parse_test_files_option,
                          metafunc.config.option.test_files))
    if 'case' in metafunc.fixturenames:
        base_dir = metafunc.config.option.integration_case_dir
        thirdparty = metafunc.config.option.thirdparty
        cases = list(run.collect_dir_tests(base_dir, test_files))
        if thirdparty:
            cases.extend(run.collect_dir_tests(
                os.path.join(base_dir, 'thirdparty'), test_files, True))
        ids = ["%s:%s" % (c.module_name, c.line_nr_test) for c in cases]
        metafunc.parametrize('case', cases, ids=ids)

    if 'refactor_case' in metafunc.fixturenames:
        base_dir = metafunc.config.option.refactor_case_dir
        metafunc.parametrize(
            'refactor_case',
            refactor.collect_dir_tests(base_dir, test_files))

    if 'static_analysis_case' in metafunc.fixturenames:
        base_dir = os.path.join(os.path.dirname(__file__), 'static_analysis')
        metafunc.parametrize(
            'static_analysis_case',
            collect_static_analysis_tests(base_dir, test_files))


def collect_static_analysis_tests(base_dir, test_files):
    for f_name in os.listdir(base_dir):
        files_to_execute = [a for a in test_files.items() if a[0] in f_name]
        if f_name.endswith(".py") and (not test_files or files_to_execute):
            path = os.path.join(base_dir, f_name)
            yield StaticAnalysisCase(path)


class StaticAnalysisCase(object):
    """
    Static Analysis cases lie in the static_analysis folder.
    The tests also start with `#!`, like the goto_definition tests.
    """
    def __init__(self, path):
        self.skip = False
        self._path = path
        with open(path) as f:
            self._source = f.read()

    def collect_comparison(self):
        cases = []
        for line_nr, line in enumerate(self._source.splitlines(), 1):
            match = re.match(r'(\s*)#! (\d+ )?(.*)$', line)
            if match is not None:
                column = int(match.group(2) or 0) + len(match.group(1))
                cases.append((line_nr + 1, column, match.group(3)))
        return cases

    def run(self, compare_cb):
        analysis = jedi.Script(self._source, path=self._path)._analysis()
        typ_str = lambda inst: 'warning ' if isinstance(inst, Warning) else ''
        analysis = [(r.line, r.column, typ_str(r) + r.name)
                    for r in analysis]
        compare_cb(self, analysis, self.collect_comparison())

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, os.path.basename(self._path))


@pytest.fixture()
def isolated_jedi_cache(monkeypatch, tmpdir):
    """
    Set `jedi.settings.cache_directory` to a temporary directory during test.

    Same as `clean_jedi_cache`, but create the temporary directory for
    each test case (scope='function').
    """
    from jedi import settings
    monkeypatch.setattr(settings, 'cache_directory', str(tmpdir))


@pytest.fixture(scope='session')
def clean_jedi_cache(request):
    """
    Set `jedi.settings.cache_directory` to a temporary directory during test.

    Note that you can't use built-in `tmpdir` and `monkeypatch`
    fixture here because their scope is 'function', which is not used
    in 'session' scope fixture.

    This fixture is activated in ../pytest.ini.
    """
    from jedi import settings
    old = settings.cache_directory
    tmp = tempfile.mkdtemp(prefix='jedi-test-')
    settings.cache_directory = tmp

    @request.addfinalizer
    def restore():
        settings.cache_directory = old
        shutil.rmtree(tmp)
