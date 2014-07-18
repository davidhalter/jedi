"""
Issues with the parser not the completion engine should be here.
"""

class C():
    """
    issue jedi-vim#288
    Which is really a fast parser issue. It used to start a new block at the
    parentheses, because it had problems with the indentation.
    """
    def indent_issues(
        self,
    ):
        return 1


#? int()
C().indent_issues()
