import sys

import pytest


@pytest.mark.skipif(sys.version_info[0] == 2, reason="Ignore Python 2, because EOL")
def test_issue436(Script, skip_python2):
    code = "bar = 0\nbar += 'foo' + 4"
    errors = set(repr(e) for e in Script(code)._analysis())
    assert len(errors) == 2
    assert '<Error type-error-operation: None@2,4>' in errors
    assert '<Error type-error-operation: None@2,13>' in errors
