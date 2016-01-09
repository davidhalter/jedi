import tempfile
import shutil

import pytest

import jedi

collect_ignore = ["setup.py"]


# The following hooks (pytest_configure, pytest_unconfigure) are used
# to modify `jedi.settings.cache_directory` because `clean_jedi_cache`
# has no effect during doctests.  Without these hooks, doctests uses
# user's cache (e.g., ~/.cache/jedi/).  We should remove this
# workaround once the problem is fixed in py.test.
#
# See:
# - https://github.com/davidhalter/jedi/pull/168
# - https://bitbucket.org/hpk42/pytest/issue/275/

jedi_cache_directory_orig = None
jedi_cache_directory_temp = None


def pytest_addoption(parser):
    parser.addoption("--jedi-debug", "-D", action='store_true',
                     help="Enables Jedi's debug output.")

    parser.addoption("--warning-is-error", action='store_true',
                     help="Warnings are treated as errors.")


def pytest_configure(config):
    global jedi_cache_directory_orig, jedi_cache_directory_temp
    jedi_cache_directory_orig = jedi.settings.cache_directory
    jedi_cache_directory_temp = tempfile.mkdtemp(prefix='jedi-test-')
    jedi.settings.cache_directory = jedi_cache_directory_temp

    if config.option.jedi_debug:
        jedi.set_debug_function()

    if config.option.warning_is_error:
        import warnings
        warnings.simplefilter("error")


def pytest_unconfigure(config):
    global jedi_cache_directory_orig, jedi_cache_directory_temp
    jedi.settings.cache_directory = jedi_cache_directory_orig
    shutil.rmtree(jedi_cache_directory_temp)


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
