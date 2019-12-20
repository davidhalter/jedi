def test_import_references(Script):
    s = Script("from .. import foo", path="foo.py")
    assert [usage.line for usage in s.find_references(line=1, column=18)] == [1]


def test_exclude_builtin_modules(Script):
    def get(include):
        references = Script(source).find_references(column=8, include_builtins=include)
        return [(d.line, d.column) for d in references]
    source = '''import sys\nprint(sys.path)'''
    places = get(include=True)
    assert len(places) > 2  # Includes stubs

    places = get(include=False)
    assert places == [(1, 7), (2, 6)]
