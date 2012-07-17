
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
        a = 3

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
        # should not know any class functions!
        #? []
        values
        #? []
        ret
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

#? int()
inst.var_local
#? []
TestClass.var_local.

#? int()
TestClass().ret(1)
#? int()
inst.ret(1)

myclass = TestClass(1, '', 3.0)
#? int()
myclass.get_first()
#? []
myclass.get_first.real

# too many params
#? int()
TestClass(1,1,1).var_inst

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
#? float()
ints.second
#? str()
strs.second

#? ['var_class']
TestClass.var_class.var_class.var_class.var_class

# -----------------
# inheritance
# -----------------

class Base(object):
    def method_base(self):
        return 1

class SuperClass(Base):
    class_super = 3
    def __init__(self):
        self.var_super = ''
    def method_super(self):
        self.var2_super = list

class Mixin(SuperClass):
    def method_mixin(self):
        return int

class SubClass(SuperClass):
    class_sub = 3
    def __init__(self):
        self.var_sub = ''
    def method_sub(self):
        self.var_sub = list
        return tuple

instance = SubClass()

#? ['method_base', 'method_sub', 'method_super']
instance.method_
#? ['var2_super', 'var_sub', 'var_super']
instance.var
#? ['class_sub', 'class_super']
instance.class_

#? ['method_base', 'method_sub', 'method_super']
SubClass.method_
#? []
SubClass.var
#? ['class_sub', 'class_super']
SubClass.class_

# -----------------
# __call__
# -----------------

class CallClass():
    def __call__(self):
        return 1

#? int()
CallClass()()

# -----------------
# properties
# -----------------

class B():
    @property
    def r(self):
        return 1
    @r.setter
    def r(self, value):
        pass
    def t(self):
        return ''
    ##p = property(t)

#? []
B().r()
#? int()
B().r

##? str()
B().p
##? []
B().p()

# -----------------
# variable assignments
# -----------------

class V:
    def __init__(self):
        self.a = 1

    def ret(self):
        return self.a

    b = ret

##? int()
V().b()

# -----------------
# ordering
# -----------------
class A():
    def b(self):
        #? int()
        a()
        #? str()
        self.a()
        return a()

    def a(self):
        return ""

def a():
    return 1

#? int()
A().b()
#? str()
A().a()

# -----------------
# nested classes
# -----------------
class A():
    class B():
        pass
    def b(self):
        return 1.0

#? float()
A().b()

class A():
    def b(self):
        class B():
            def b(self):
                return []
        return B().b()

#? list()
A().b()
