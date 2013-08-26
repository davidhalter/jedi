from jedi import builtin


def test_parse_function_doc_illegal_docstr():

    def test_func(a):
        """
        test_func(o

        doesn't have a closing bracket.
        """

    assert ('', '') == builtin._parse_function_doc(test_func)
