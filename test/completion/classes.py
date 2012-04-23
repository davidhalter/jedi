
class TestClass(object):
    var_class = TestClass()

    def __init__(self2, a):
        self2.var_inst = a

    def values(self):
        self.var_local = 3
        #? ['var_class', 'var_inst', 'var_local']
        self.var_

inst = TestClass(1)

#? ['var_class', 'var_inst', 'var_local']
inst.var

#? ['var_class']
TestClass.var_class
