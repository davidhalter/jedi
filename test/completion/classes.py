
# set variables, which should not be included, because they don't belong to the
# class
second = 1
second = ""
class TestClass(object):
    var_class = TestClass(1)

    def __init__(self2, first_param, second_param):
        self2.var_inst = first_param
        self2.second = second_param
        self2.first = first_param

    def var_func(self):
        return 1

    def get_first(self):
        # traversal
        self.second_new = self.second
        return self.var_inst

    def values(self):
        self.var_local = 3
        #? ['var_class', 'var_func', 'var_inst', 'var_local']
        self.var_

    def ret(self, a1):
        return a1

inst = TestClass(1)

#? ['var_class', 'var_func', 'var_inst', 'var_local']
inst.var

#? ['var_class', 'var_func']
TestClass.var

#? ['real']
inst.var_local.real
#? []
TestClass.var_local.real

#? ['real']
TestClass().ret(1).real
#? ['real']
inst.ret(1).real

myclass = TestClass(1, '')
#? ['real']
myclass.get_first().real
#? []
myclass.get_first().upper
#? []
myclass.get_first.real

# too many params
#? ['real']
TestClass(1,1,1).var_inst.real

# too few params
#? ['real']
TestClass(1).first.real
#? []
TestClass(1).second.real

# complicated variable settings in class
#? ['upper']
myclass.second.upper
#? []
myclass.second.real
#? ['upper']
myclass.second_new.upper
#? []
myclass.second_new.real

# multiple classes / ordering
ints = TestClass(1, 1.0)
strs = TestClass("", '')
#? ['real']
ints.second.real
#? ['upper']
strs.second.upper

#? ['var_class']
TestClass.var_class.var_class.var_class.var_class
