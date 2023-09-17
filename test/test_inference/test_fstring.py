from textwrap import dedent


def test_fstring_multiline(Script):
    code = dedent("""\
        '' f'''s{
           str.uppe
        '''
        """)
    c, = Script(code).complete(line=2, column=9)
    assert c.name == 'upper'
