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
#? []
exe[3][0]
#? str()
exe[4]['d']


exe = fu(list, set, 3, '', d='')

#? str()
exe[3][0]

# -----------------
# multiple decorators
# -----------------
def dec2(func2):
    def wrapper2(first_arg, *args2, **kwargs2):
        return func2(first_arg, *args2, **kwargs2)
    return wrapper2

@dec2
@dec
def fu2(a, b, c, *args, **kwargs):
    return a, b, c, args, kwargs

exe = fu2(list, c=set, b=3, d='str')

#? list()
exe[0]
#? int()
exe[1]
#? set
exe[2]
#? []
exe[3][0]
#? str()
exe[4]['d']


# -----------------
# Decorator is a class
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
# method decorators
# -----------------

def dec(f):
    def wrapper(s):
        return f(s)
    return wrapper

class MethodDecorators():
    _class_var = 1
    def __init__(self):
        self._method_var = ''

    @dec
    def constant(self):
        return 1.0

    @dec
    def class_var(self):
        return self._class_var

    @dec
    def method_var(self):
        return self._method_var

#? float()
MethodDecorators().constant()
#? int()
MethodDecorators().class_var()
#? str()
MethodDecorators().method_var()

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

# -----------------
# class decorators
# -----------------

# class decorators should just be ignored
@should_ignore
class A(): pass

