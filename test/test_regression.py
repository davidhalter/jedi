"""
Unit tests to avoid errors of the past. These are also all tests that didn't
found a good place in any other testing module.
"""

import textwrap


def check_definition_by_marker(Script, source, after_cursor, names):
    r"""
    Find definitions specified by `after_cursor` and check what found

    For example, for the following configuration, you can pass
    ``after_cursor = 'y)'``.::

        function(
            x, y)
               \
                `- You want cursor to be here
    """
    source = textwrap.dedent(source)
    for (i, line) in enumerate(source.splitlines()):
        if after_cursor in line:
            break
    column = len(line) - len(after_cursor)
    defs = Script(source, i + 1, column).goto_definitions()
    assert [d.name for d in defs] == names


def test_backslash_continuation(Script):
    """
    Test that ModuleWithCursor.get_path_until_cursor handles continuation
    """
    check_definition_by_marker(Script, r"""
    x = 0
    a = \
      [1, 2, 3, 4, 5, 6, 7, 8, 9, x]  # <-- here
    """, ']  # <-- here', ['int'])

    # completion in whitespace
    s = 'asdfxyxxxxxxxx sds\\\n    hello'
    assert Script(s, 2, 4).goto_assignments() == []


def test_backslash_continuation_and_bracket(Script):
    check_definition_by_marker(Script, r"""
    x = 0
    a = \
      [1, 2, 3, 4, 5, 6, 7, 8, 9, (x)]  # <-- here
    """, '(x)]  # <-- here', ['int'])
