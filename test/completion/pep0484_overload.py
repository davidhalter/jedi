# python >= 3.4
from typing import List, Dict, overload


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


@overload
def overload_f3(value: list) -> str: ...
@overload
def overload_f3(value: dict) -> float: ...

#? str()
overload_f3([''])
#? float()
overload_f3({1.0: 1.0})
