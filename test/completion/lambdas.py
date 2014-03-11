# -----------------
# lambdas
# -----------------
a = lambda: 3
#? int()
a()

x = []
a = lambda x: x
#? int()
a(0)

#? float()
(lambda x: x)(3.0)

arg_l = lambda x, y: y, x
#? float()
arg_l[0]('', 1.0)
#? list()
arg_l[1]

arg_l = lambda x, y: (y, x)
args = 1,""
result = arg_l(*args)
#? tuple()
result
#? str()
result[0]
#? int()
result[1]

def with_lambda(callable_lambda, *args, **kwargs):
    return callable_lambda(1, *args, **kwargs)

#? int()
with_lambda(arg_l, 1.0)[1]
#? float()
with_lambda(arg_l, 1.0)[0]
#? float()
with_lambda(arg_l, y=1.0)[0]
#? int()
with_lambda(lambda x: x)
#? float()
with_lambda(lambda x, y: y, y=1.0)

arg_func = lambda *args, **kwargs: (args[0], kwargs['a'])
#? int()
arg_func(1, 2, a='', b=10)[0]
#? list()
arg_func(1, 2, a=[], b=10)[1]

# magic method
a = lambda: 3
#? ['__closure__']
a.__closure__

class C():
    def __init__(self):
        self.a = lambda: 1
#? int()
C().a()


# -----------------
# lambda param (#379)
# -----------------
class Test(object):
    def __init__(self, pred=lambda a, b: a):
        self.a = 1
        #? int()
        self.a
        #? float()
        pred(1.0, 2)
