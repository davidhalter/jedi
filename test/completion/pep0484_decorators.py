""" Pep-0484 type hinted decorators """

from typing import Callable


def decorator(func):
    def wrapper(*a, **k):
        return str(func(*a, **k))
    return wrapper


def typed_decorator(func: Callable[..., int]) -> Callable[..., str]:
    ...

# Functions

@decorator
def plain_func() -> int:
    return 4

#? str()
plain_func()


@typed_decorator
def typed_func() -> int:
    return 4

#? str()
typed_func()


# Methods

class X:
    @decorator
    def plain_method(self) -> int:
        return 4

    @typed_decorator
    def typed_method(self) -> int:
        return 4

inst = X()

#? str()
inst.plain_method()

#? str()
inst.typed_method()
