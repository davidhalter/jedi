"""
Special cases of completions (typically special positions that caused issues
with value parsing.
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
#? 5 []
tuple,
          ):
        return 1


if x:
    pass
#? ['else']
else

# python >= 3.11
try:
    pass
#? ['except', 'Exception', 'ExceptionGroup']
except

try:
    pass
#? 6 ['except', 'Exception', 'ExceptionGroup']
except AttributeError:
    pass
#? ['finally']
finally

for x in y:
    pass
#? ['else']
else
