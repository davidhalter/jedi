"""
Test all things related to the ``jedi.cache`` module.
"""

import jedi


def test_cache_call_signatures():
    """
    See github issue #390.
    """
    def check(column, call_name, path=None):
        assert jedi.Script(s, 1, column, path).call_signatures()[0].name == call_name

    s = 'str(int())'

    for i in range(3):
        check(8, 'int')
        check(4, 'str')
        # Can keep doing these calls and always get the right result.

    # Now lets specify a source_path of boo and alternate these calls, it
    # should still work.
    for i in range(3):
        check(8, 'int', 'boo')
        check(4, 'str', 'boo')


def test_cache_line_split_issues():
    """Should still work even if there's a newline."""
    assert jedi.Script('int(\n').call_signatures()[0].name == 'int'
