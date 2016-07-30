"""
Special cases of completions (typically special positions that caused issues
with context parsing.
"""

def pass_decorator(func):
    return func


def x():
    return (
        1,
#? ["tuple"]
tuple
    )

    # Comment just somewhere


class MyClass:
    @pass_decorator
    def x(foo,
#? 5 ["tuple"]
tuple,
          ):
        return 1
