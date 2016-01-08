from textwrap import dedent

from jedi import names
from jedi.evaluate import helpers


def test_call_of_name_in_brackets():
    s = dedent("""
    x = 1
    type(x)
    """)
    last_x = names(s, references=True, definitions=False)[-1]
    name = last_x._name

    call = helpers.call_of_name(name)
    assert call == name
