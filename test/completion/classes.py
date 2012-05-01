
class TestClass(object):
    var_class = TestClass(1)

    def __init__(self2, first_param, second_param):
        self2.var_inst = first_aparam
        self2.second = second_param

    def get_var_inst(self):
        # traversal
        self.second_new = self.second
        return self.var_inst

    def values(self):
        self.var_local = 3
        #? ['var_class', 'var_inst', 'var_local']
        self.var_

    def ret(self, a1):
        return a1

inst = TestClass(1)

#? ['var_class', 'var_inst', 'var_local']
inst.var

#? ['var_class']
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
TestClass(1).var_inst.
#? ['real']
myclass.get_var_inst().real
#? []
myclass.get_var_inst().upper
#? []
myclass.get_var_inst.real
