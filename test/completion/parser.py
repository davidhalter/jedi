"""
Issues with the parser not the completion engine should be here.
"""

class IndentIssues():
    """
    issue jedi-vim#288
    Which is really a fast parser issue. It used to start a new block at the
    parentheses, because it had problems with the indentation.
    """
    def one_param(
        self,
    ):
        return 1

    def with_param(
        self,
    y):
        return y



#? int()
IndentIssues().one_param()

#? str()
IndentIssues().with_param('')


"""
Just because there's a def keyword, doesn't mean it should not be able to
complete to definition.
"""
definition = 0
#? ['definition', 'def']
str(def
