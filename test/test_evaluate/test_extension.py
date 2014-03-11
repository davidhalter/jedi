"""
Test compiled module
"""
import os
import platform
import sys
import jedi

from ..helpers import cwd_at


@cwd_at('test/test_evaluate/extensions')
def test_completions():
    if platform.architecture()[0] == '64bit':
        package_name = "compiled%s%s" % sys.version_info[:2]
        sys.path.insert(0, os.getcwd())
        if os.path.exists(package_name):
            s = jedi.Script("from %s import compiled; compiled." % package_name)
            assert len(s.completions()) >= 2


@cwd_at('test/test_evaluate/extensions')
def test_call_signatures_extension():
    # with a cython extension
    if platform.architecture()[0] == '64bit':
        package_name = "compiled%s%s" % sys.version_info[:2]
        sys.path.insert(0, os.getcwd())
        if os.path.exists(package_name):
            s = jedi.Script("from %s import compiled; compiled.Foo(" %
                            package_name)
            defs = s.call_signatures()
            for call_def in defs:
                for param in call_def.params:
                    pass


def test_call_signatures_stdlib():
    code = "import math; math.cos("
    s = jedi.Script(code)
    defs = s.call_signatures()
    for call_def in defs:
        assert len(call_def.params) == 1
