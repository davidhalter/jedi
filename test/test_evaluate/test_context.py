def test_module_attributes(Script):
    def_, = Script('__name__').completions()
    assert def_.name == '__name__'
    assert def_.line is None
    assert def_.column is None
    str_, = def_._goto_definitions()
    assert str_.name == 'str'
