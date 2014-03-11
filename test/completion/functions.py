def array(first_param):
    #? ['first_param']
    first_param
    return list()

#? []
array.first_param
#? []
array.first_param.
func = array
#? []
func.first_param

#? list()
array()

#? ['array']
arr


def inputs(param):
    return param

#? list()
inputs(list)

def variable_middle():
    var = 3
    return var

#? int()
variable_middle()

def variable_rename(param):
    var = param
    return var

#? int()
variable_rename(1)

def multi_line_func(a, # comment blabla

                    b):
    return b

#? str()
multi_line_func(1,'')

# nothing after comma
def asdf(a):
    return a

x = asdf(a=1,
    )
#? int()
x

# -----------------
# double execution
# -----------------
def double_exe(param):
    return param

#? str()
variable_rename(double_exe)("")

# -> shouldn't work (and throw no error)
#? []
variable_rename(list())().
#? []
variable_rename(1)().

# -----------------
# recursions (should ignore)
# -----------------
def recursion(a, b):
    if a:
        return b
    else:
        return recursion(a+".", b+1)

# Does not also return int anymore, because we now support operators in simple cases.
#? float()
recursion("a", 1.0)

def other(a):
    return recursion2(a)

def recursion2(a):
    if a:
        return other(a)
    else:
        return recursion2("")
    return a

#? int() str()
recursion2(1)

# -----------------
# ordering
# -----------------

def a():
    #? int()
    b()
    return b()

def b():
    return 1

#? int()
a()

# -----------------
# keyword arguments
# -----------------

def func(a=1, b=''):
    return a, b

exe = func(b=list, a=tuple)
#? tuple
exe[0]

#? list
exe[1]

# -----------------
# default arguments
# -----------------

#? int()
func()[0]
#? str()
func()[1]
#? float()
func(1.0)[0]
#? str()
func(1.0)[1]

# -----------------
# closures
# -----------------
def a():
    l = 3
    def func_b():
        #? str()
        l = ''
    #? ['func_b']
    func_b
    #? int()
    l

# -----------------
# *args
# -----------------

def args_func(*args):
    #? tuple()
    return args

exe = args_func(1, "")
#? int()
exe[0]
#? str()
exe[1]

# illegal args (TypeError)
#? 
args_func(*1)[0]
# iterator
#? int()
args_func(*iter([1]))[0]

# different types
e = args_func(*[1+"", {}])
#? int() str()
e[0]
#? dict()
e[1]

_list = [1,""]
exe2 = args_func(_list)[0]

#? str()
exe2[1]

exe3 = args_func([1,""])[0]

#? str()
exe3[1]

def args_func(arg1, *args):
    return arg1, args

exe = args_func(1, "", list)
#? int()
exe[0]
#? tuple()
exe[1]
#? list()
exe[1][1]

# -----------------
# ** kwargs
# -----------------
def kwargs_func(**kwargs):
    #? ['keys']
    kwargs.keys
    #? dict()
    return kwargs

exe = kwargs_func(a=3,b=4.0)
#? dict()
exe
#? int()
exe['a']
#? float()
exe['b']
#? int() float()
exe['c']

exe2 = kwargs_func(**{a:3,
                      b:4.0})
#? int()
exe2['a']

# -----------------
# *args / ** kwargs
# -----------------

def func_without_call(*args, **kwargs):
    #? tuple()
    args
    #? dict()
    kwargs

def fu(a=1, b="", *args, **kwargs):
    return a, b, args, kwargs

exe = fu(list, 1, "", c=set, d="")

#? list()
exe[0]
#? int()
exe[1]
#? tuple()
exe[2]
#? str()
exe[2][0]
#? dict()
exe[3]
#? set()
exe[3]['c']

# -----------------
# nested *args
# -----------------
def function_args(a, b, c):
    return b

def nested_args(*args):
    return function_args(*args)

def nested_args2(*args, **kwargs):
    return nested_args(*args)

#? int()
nested_args('', 1, 1.0, list)
#? []
nested_args('')

#? int()
nested_args2('', 1, 1.0)
#? []
nested_args2('')

# -----------------
# nested **kwargs
# -----------------
def nested_kw(**kwargs1):
    return function_args(**kwargs1)

def nested_kw2(**kwargs2):
    return nested_kw(**kwargs2)

#? int()
nested_kw(b=1, c=1.0, list)
#? int()
nested_kw(b=1)
#? int()
nested_kw(d=1.0, b=1, list)
#? int()
nested_kw(b=1)
#? int()
nested_kw(a=3.0, b=1)
#? int()
nested_kw(b=1, a=r"")
#? []
nested_kw('')
#? []
nested_kw(a='')

#? int()
nested_kw2(b=1)
#? int()
nested_kw2(b=1, c=1.0)
#? int()
nested_kw2(c=1.0, b=1)
#? []
nested_kw2('')
#? []
nested_kw2(a='')
#? []
nested_kw2('', b=1).

# -----------------
# nested *args/**kwargs
# -----------------
def nested_both(*args, **kwargs):
    return function_args(*args, **kwargs)

def nested_both2(*args, **kwargs):
    return nested_both(*args, **kwargs)

#? int()
nested_both('', b=1, c=1.0, list)
#? int()
nested_both('', c=1.0, b=1, list)
#? []
nested_both('')

#? int()
nested_both2('', b=1, c=1.0)
#? int()
nested_both2('', c=1.0, b=1)
#? []
nested_both2('')

# -----------------
# nested *args/**kwargs with a default arg
# -----------------
def function_def(a, b, c):
    return a, b

def nested_def(a, *args, **kwargs):
    return function_def(a, *args, **kwargs)

def nested_def2(*args, **kwargs):
    return nested_def(*args, **kwargs)

#? str()
nested_def2('', 1, 1.0)[0]
#? str()
nested_def2('', b=1, c=1.0)[0]
#? str()
nested_def2('', c=1.0, b=1)[0]
#? int()
nested_def2('', 1, 1.0)[1]
#? int()
nested_def2('', b=1, c=1.0)[1]
#? int()
nested_def2('', c=1.0, b=1)[1]
#? []
nested_def2('')[1]

# -----------------
# function annotations (should be ignored at the moment)
# -----------------
def annot(a:3, *args:3):
    return a, args[0]

#? str()
annot('', 1.0)[0]
#? float()
annot('', 1.0)[1]

def annot_ret(a:3) -> 3:
    return a

#? str()
annot_ret('')

# -----------------
# magic methods
# -----------------
def a(): pass
#? ['__closure__']
a.__closure__
