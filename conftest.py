import tempfile
import shutil

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


def pytest_configure(config):
    global jedi_cache_directory_orig, jedi_cache_directory_temp
    jedi_cache_directory_orig = jedi.settings.cache_directory
    jedi_cache_directory_temp = tempfile.mkdtemp(prefix='jedi-test-')
    jedi.settings.cache_directory = jedi_cache_directory_temp


def pytest_unconfigure(config):
    global jedi_cache_directory_orig, jedi_cache_directory_temp
    jedi.settings.cache_directory = jedi_cache_directory_orig
    shutil.rmtree(jedi_cache_directory_temp)
