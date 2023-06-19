# python >= 3.9

from typing import Annotated

# This is just a dummy and very meaningless thing to use with to the Annotated
# type hint
class Foo:
    pass

class A:
    pass


def annotated_function_params(
    basic: Annotated[str, Foo()],
    obj: A,
    annotated_obj: Annotated[A, Foo()],
):
    #? str()
    basic

    #? A()
    obj

    #? A()
    annotated_obj
