"""
PEP 526 introduced a new way of using type annotations on variables. It was
introduced in Python 3.6.
"""
# python >= 3.6

import typing

asdf = ''
asdf: int
# This is not necessarily correct, but for now this is ok (at least no error).
#? int()
asdf


direct: int = NOT_DEFINED
#? int()
direct

with_typing_module: typing.List[float] = NOT_DEFINED
#? float()
with_typing_module[0]
