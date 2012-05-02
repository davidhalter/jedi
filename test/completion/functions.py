
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
