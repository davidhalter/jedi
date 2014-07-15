"""
Issues with the parser not the completion engine should be here.
"""

class C():
    """ issue jedi-vim#288 """
    def indent_issues(
        self,
    ):
        return 1


#? int()
C().indent_issues()
