# python >= 3.6
from typing import List, Dict, overload

lst: list
list_alias: List
list_str: List[str]

# -------------------------
# With base classes
# -------------------------

@overload
def overload_f2(value: List) -> str: ...
@overload
def overload_f2(value: Dict) -> int: ...

#? str()
overload_f2([''])
#? int()
overload_f2({1.0: 1.0})
#? str()
overload_f2(lst)
#? str()
overload_f2(list_alias)
#? str()
overload_f2(list_str)


@overload
def overload_f3(value: list) -> str: ...
@overload
def overload_f3(value: dict) -> float: ...

#? str()
overload_f3([''])
#? float()
overload_f3({1.0: 1.0})
#? str()
overload_f3(lst)
#? str()
overload_f3(list_alias)
#? str()
overload_f3(list_str)
