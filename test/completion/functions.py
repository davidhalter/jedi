
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

#? ['append']
array().append

#? ['array']
arr


def inputs(param):
    return param

#? ['append']
inputs(list).append

def variable_middle():
    var = 3
    return var

#? ['real']
variable_middle().real

def variable_rename(param):
    var = param
    return var

#? ['imag']
variable_rename(1).imag

# -----------------
# double execution
# -----------------
def double_exe(param):
    return param

#? ['upper']
variable_rename(double_exe)("").upper

# -> shouldn't work (and throw no error)
#? []
variable_rename(list())().
#? []
variable_rename(1)().

# -----------------
# recursion (should ignore)
# -----------------
def recursion(a, b):
    if a:
        return b
    else:
        return recursion(a+".", b+1)

##? int() float()
recursion("a", 1.0)

# -----------------
# keyword arguments
# -----------------

def func(a=1, b=''):
    return a, b

exe = func(b=list, a=tuple)
#? tuple()
exe[0]

#? list()
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
        #? ['real']
        l.real
        l = ''
    #? ['func_b']
    func_b
    #? ['real']
    l.real

# -----------------
# *args
# -----------------

def args_func(*args):
    return args

exe = args_func(1, "")
#? int()
exe[0]

#? str()
exe[1]

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
    return kwargs

exe = kwargs_func(a=3,b=4)
#? ['items']
exe.items

# -----------------
# *args / ** kwargs
# -----------------

def fu(a=1, b="", *args, **kwargs):
    return a, b, args, kwargs

exe = fu(list, 1, "", c=set, d="")

#? ['append']
exe[0].append
#? ['real']
exe[1].real
#? ['index']
exe[2].index
#? ['upper']
exe[2][0].upper
#? ['items']
exe[3].items
#? set()
exe[3]['c']

