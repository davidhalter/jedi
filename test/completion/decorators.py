# -----------------
# normal decorators
# -----------------

def decorator(func):
    def wrapper(*args):
        return func(1, *args)
    return wrapper

@decorator
def decorated(a,b):
    return a,b

exe = decorated(set, '')

#? set
exe[1]

#? int()
exe[0]

# more complicated with args/kwargs
def dec(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@dec
def fu(a, b, c, *args, **kwargs):
    return a, b, c, args, kwargs

exe = fu(list, c=set, b=3, d='')

#? list()
exe[0]
#? int()
exe[1]
#? set
exe[2]

#? str()
exe[4]['d']


exe = fu(list, set, 3, '', d='')

#? str()
exe[3][0]

# -----------------
# class decorators
# -----------------
class Decorator(object):
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(1, *args, **kwargs)

@Decorator
def nothing(a,b,c):
    return a,b,c

#? int()
nothing("")[0]
#? str()
nothing("")[1]

# -----------------
# properties
# -----------------

class PropClass():
    def __init__(self, a):
        self.a = a
    @property
    def ret(self):
        return self.a

#? str()
PropClass("").ret

#? []
PropClass().ret.

# -----------------
# not found decorators
# -----------------
@not_found_decorator
def just_a_func():
    return 1

#? []
just_a_func()

#? []
just_a_func.


class JustAClass:
    @not_found_decorator2
    def a(self):
        return 1

#? []
JustAClass().a.
#? []
JustAClass().a()
#? []
JustAClass.a.
#? []
JustAClass().a()

# -----------------
# others
# -----------------
def memoize(function):
        def wrapper(*args):
            if 1:
                pass
            else:
                rv = function(*args)
                return rv
        return wrapper

@memoize
def follow_statement(stmt):
    return stmt

# here we had problems with the else clause, because the parent was not right.
#? int()
follow_statement(1)
