# python >= 3.12

# -----------------
# new generic syntax should not fail
# -----------------

class C[T]:
    def c(self) -> str: ...
def f[T](x: T, y: T) -> int: ...

#? int()
f()
#? str()
C().c()
