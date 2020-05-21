def test_import_references(Script):
    s = Script("from .. import foo", path="foo.py")
    assert [usage.line for usage in s.get_references(line=1, column=18)] == [1]


def test_exclude_builtin_modules(Script):
    def get(include):
        from jedi.api.project import Project
        script = Script(source, project=Project('', sys_path=[], smart_sys_path=False))
        references = script.get_references(column=8, include_builtins=include)
        return [(d.line, d.column) for d in references]
    source = '''import sys\nprint(sys.path)'''
    places = get(include=True)
    assert len(places) > 2  # Includes stubs

    places = get(include=False)
    assert places == [(1, 7), (2, 6)]


def test_references_scope(Script):
    from jedi.api.project import Project
    project = Project('', sys_path=[], smart_sys_path=False)
    script = Script(
        '''import sys
from collections import defaultdict

print(sys.path)

def foo(bar):
    baz = defaultdict(int)
    return baz

def bar(foo):
    baz = defaultdict(int)
    return baz

foo()
''', project=project)

    def r(*args):
        return script.get_references(all_scopes=False, *args)

    print(script._code_lines)
    sys_places = r(1, 7)
    assert len(sys_places) == 2
    assert sys_places == r(4, 6)

    assert len(r(2, 5)) == 1

    dd_places = r(2, 24)
    assert len(dd_places) == 3
    assert dd_places == r(7, 10)
    assert dd_places == r(11, 10)

    foo_places = r(6, 4)
    assert len(foo_places) == 2
    assert foo_places == r(14, 0)

    baz_places = r(7, 4)
    assert len(baz_places) == 2
    assert baz_places == r(8, 11)

    int_places = r(7, 22)
    assert len(int_places) == 2
    assert int_places == r(11, 22)

    baz_places = r(11, 4)
    assert len(baz_places) == 2
    assert baz_places == r(12, 11)

    script = Script('from datetime', project=project)
    places = r(1, 5)
    assert len(places) == 1
