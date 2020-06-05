import pytest


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


@pytest.mark.parametrize('code, places', [
    ('', [(1, 7), (4, 6)]),
    ('', [(2, 5)]),
    ('', [(2, 24), (7, 10), (11, 10)]),
    ('', [(6, 4), (14, 0)]),
    ('', [(7, 4), (8, 11)]),
    ('', [(7, 22), (11, 22)]),
    ('', [(11, 4), (12, 11)]),
    ('from datetime', [(1, 5)]),
    ('''from datetime import datetime
d1 = datetime.now()
d2 = datetime.now()
''', [(2, 14), (3, 14)]),
    ('''from datetime import timedelta
t1 = timedelta(seconds=1)
t2 = timedelta(seconds=2)
''', [(2, 15), (3, 15)])
])
def test_references_scope(Script, code, places):
    if not code:
        code = '''import sys
from collections import defaultdict

print(sys.path)

def foo(bar):
    baz = defaultdict(int)
    return baz

def bar(foo):
    baz = defaultdict(int)
    return baz

foo()
'''
    from jedi.api.project import Project
    project = Project('', sys_path=[], smart_sys_path=False)
    script = Script(code, project=project)

    for place in places:
        assert places == [(n.line, n.column) for n in script.get_references(scope='file', *place)]
