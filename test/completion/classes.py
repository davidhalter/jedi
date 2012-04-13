
class TestClass(object):
    var_class = TestClass()

    def __init__(self2, a):
        self2.var_inst = a



inst = TestClass(1)

#? ['var_class', 'var_inst']
inst.var

#? ['var_class']
TestClass.var_class


