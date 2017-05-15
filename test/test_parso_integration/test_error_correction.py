import jedi


def test_error_correction_with():
    source = """
    with open() as f:
        try:
            f."""
    comps = jedi.Script(source).completions()
    assert len(comps) > 30
    # `open` completions have a closed attribute.
    assert [1 for c in comps if c.name == 'closed']
