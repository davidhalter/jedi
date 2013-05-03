def find_class():
    """ This scope is special, because its in front of TestClass """
    #? ['ret']
    TestClass.ret
    if 1:
        #? ['ret']
        TestClass.ret

class FindClass():
    #? []
    TestClass.ret
    if a:
        #? []
        TestClass.ret

    def find_class(self):
        #? ['ret']
        TestClass.ret
        if 1:
            #? ['ret']
            TestClass.ret

#? []
FindClass().find_class.self
#? []
FindClass().find_class.self.find_class

# set variables, which should not be included, because they don't belong to the
# class
second = 1
second = ""
class TestClass(object):
    var_class = TestClass(1)

    def __init__(self2, first_param, second_param, third=1.0):
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
        #? ['return']
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
# variable assignments
# -----------------

class V:
    def __init__(self, a):
        self.a = a

    def ret(self):
        return self.a

    d = b
    b = ret
    if 1:
        c = b

#? int()
V(1).b()
#? int()
V(1).c()
#? []
V(1).d()


# -----------------
# ordering
# -----------------
class A():
    def b(self):
        #? int()
        a_func()
        #? str()
        self.a_func()
        return a_func()

    def a_func(self):
        return ""

def a_func():
    return 1

#? int()
A().b()
#? str()
A().a_func()

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

# -----------------
# descriptors
# -----------------
class RevealAccess(object):
    """
    A data descriptor that sets and returns values
    normally and prints a message logging their access.
    """
    def __init__(self, initval=None, name='var'):
        self.val = initval
        self.name = name

    def __get__(self, obj, objtype):
        print('Retrieving', self.name)
        return self.val

    def __set__(self, obj, val):
        print('Updating', self.name)
        self.val = val

    def just_a_method(self):
        pass

class C(object):
    x = RevealAccess(10, 'var "x"')
    #? RevealAccess()
    x
    #? ['just_a_method']
    x.just_a_method
    y = 5.0
    def __init__(self):
        #? int()
        self.x

        #? []
        self.just_a_method
        #? []
        C.just_a_method

m = C()
#? int()
m.x
#? float()
m.y
#? int()
C.x

#? []
m.just_a_method
#? []
C.just_a_method

# -----------------
# properties
# -----------------
class B():
    @property
    def r(self):
        return 1
    @r.setter
    def r(self, value):
        return ''
    def t(self):
        return ''
    p = property(t)

#? []
B().r()
#? int()
B().r

#? str()
B().p
#? []
B().p()

class PropClass():
    def __init__(self, a):
        self.a = a
    @property
    def ret(self):
        return self.a

    @ret.setter
    def ret(self, value):
        return 1.0

    def ret2(self):
        return self.a
    ret2 = property(ret2)

    @property
    def nested(self):
        """ causes recusions in properties, should work """
        return self.ret

    @property
    def nested2(self):
        """ causes recusions in properties, should not work """
        return self.nested2

    @property
    def join1(self):
        """ mutual recusion """
        return self.join2

    @property
    def join2(self):
        """ mutual recusion """
        return self.join1

#? str()
PropClass("").ret
#? []
PropClass().ret.

#? str()
PropClass("").ret2
#? 
PropClass().ret2

#? int()
PropClass(1).nested
#? []
PropClass().nested.

#? 
PropClass(1).nested2
#? []
PropClass().nested2.

#? 
PropClass(1).join1
# -----------------
# staticmethod/classmethod
# -----------------

class E(object):
    a = ''
    def __init__(self, a):
        self.a = a

    def f(x):
        return x
    f = staticmethod(f)

    @staticmethod
    def g(x):
        return x

    def s(cls, x):
        return x
    s = classmethod(s)

    @classmethod
    def t(cls, x):
        return x

    @classmethod
    def u(cls, x):
        return cls.a

e = E(1)
#? int()
e.f(1)
#? int()
E.f(1)
#? int()
e.g(1)
#? int()
E.g(1)

#? int()
e.s(1)
#? int()
E.s(1)
#? int()
e.t(1)
#? int()
E.t(1)

#? str()
e.u(1)
#? str()
E.u(1)

# -----------------
# recursions
# -----------------
def Recursion():
    def recurse(self):
        self.a = self.a
        self.b = self.b.recurse()

#? 
Recursion().a

#? 
Recursion().b

# -----------------
# ducktyping
# -----------------

def meth(self):
    return self.a, self.b

class WithoutMethod():
    a = 1
    def __init__(self):
        self.b = 1.0
    def blub(self):
        return self.b
    m = meth

class B():
    b = ''

a = WithoutMethod().m()
#? int()
a[0]
#? float()
a[1]

#? float()
WithoutMethod.blub(WithoutMethod())
#? str()
WithoutMethod.blub(B())

# -----------------
# __getattr__ / getattr() / __getattribute__
# -----------------

#? str().upper
getattr(str(), 'upper')
#? str.upper
getattr(str, 'upper')

# some strange getattr calls
#? 
getattr(str, 1)
#? 
getattr()
#? 
getattr(str)
#? 
getattr(getattr, 1)


class Base():
    def ret(self, b):
        return b

class Wrapper():
    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, name):
        return getattr(self.obj, name)

class Wrapper2():
    def __getattribute__(self, name):
        return getattr(Base(), name)

#? int()
Wrapper(Base()).ret(3)

#? int()
Wrapper2(Base()).ret(3)

# -----------------
# private vars
# -----------------
class PrivateVar():
    def __init__(self):
        self.__var = 1
        #? int()
        self.__var
#? []
PrivateVar().__var
#? 
PrivateVar().__var

# -----------------
# super
# -----------------
class Super(object):
    a = 3

class TestSuper(Super):
    #? 
    super()
    def test(self):
        #? Super()
        super()
        #? ['a']
        super().a
        if 1:
            #? Super()
            super()
        def a():
            #? 
            super()


# -----------------
# if flow at class level
# -----------------
class TestX(object):
    def normal_method(self):
        return 1

    if True:
        def conditional_method(self):
            var = self.normal_method()
            #? int()
            var
            return 2

    def other_method(self):
        var = self.conditional_method()
        #? int()
        var
