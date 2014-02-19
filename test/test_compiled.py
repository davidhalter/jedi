"""
Test compiled module
"""
import os
import platform
import sys
import jedi

from .helpers import cwd_at


@cwd_at('test/extensions')
def test_compiled():
    if platform.architecture()[0] == '64bit':
        package_name = "compiled%s%s" % sys.version_info[:2]
        sys.path.insert(0, os.getcwd())
        if os.path.exists(package_name):
            s = jedi.Script("from %s import compiled; compiled." % package_name)
            assert len(s.completions()) >= 2
