def test_import_usage(Script):
    s = Script("from .. import foo", line=1, column=18, path="foo.py")
    assert [usage.line for usage in s.usages()] == [1]
