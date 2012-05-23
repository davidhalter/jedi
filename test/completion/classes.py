
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

# should not work
#? []
var_local
#? []
var_inst
#? []
var_func

# instance
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
#? int()
myclass.get_first()
#? []
myclass.get_first.real

# too many params
#? ['real']
TestClass(1,1,1).var_inst.real

# too few params
#? int()
TestClass(1).first
#? []
TestClass(1).second.

# complicated variable settings in class
#? str()
myclass.second
#? str()
myclass.second_new

# multiple classes / ordering
ints = TestClass(1, 1.0)
strs = TestClass("", '')
#? ['real']
ints.second.real
#? ['upper']
strs.second.upper

#? ['var_class']
TestClass.var_class.var_class.var_class.var_class

# -----------------
# inheritance
# -----------------

class SuperClass(object):
    class_super = 3
    def __init__(self):
        self.var_super = ''
    def method_super(self):
        self.var2_super = list

class Mixin(SuperClass):
    def method_super(self):
        return int

class SubClass(SuperClass):
    class_sub = 3
    def __init__(self):
        self.var_sub = ''
    def method_sub(self):
        self.var_sub = list
        return tuple

instance = SubClass()

#? ['method_sub', 'method_super']
instance.method_
#? ['var2_super', 'var_sub', 'var_super']
instance.var
#? ['class_sub', 'class_super']
instance.class_

#? ['method_sub', 'method_super']
SubClass.method_
#? []
SubClass.var
#? ['class_sub', 'class_super']
SubClass.class_
