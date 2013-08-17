"""
Renaming tests. This means search for usages.
I always leave a little bit of space to add room for additions, because the
results always contain position informations.
"""
#< 4 (0,4), (3,0), (5,0)
def abc(): pass

#< 0 (-3,4), (0,0), (2,0)
abc.d.a.bsaasd.abc.d

abc

abc = 

#< (-3,0), (0,0)
abc


Abc = 3

#< 6 (0,6), (2,4), (5,8), (17,0)
class Abc():
    #< (-2,6), (0,4), (3,8), (15,0)
    Abc

    def Abc(self):
        Abc; self.c = 3

    #< 17 (0,16), (2,8)
    def a(self, Abc):
        #< 10 (-2,16), (0,8)
        Abc

    #< 19 (0,18), (2,8)
    def self_test(self):
        #< 12 (-2,18), (0,8)
        self.b

Abc.d.Abc


#< 4 (0,4), (4,1)
def blub():


#< (-4,4), (0,1)
@blub
def a(): pass


#< 0 (0,0), (1,0)
set_object_var = object()
set_object_var.var = 1


response = 5
#< 0 (0,0), (1,0), (2,0), (4,0)
response = HttpResponse(mimetype='application/pdf')
response['Content-Disposition'] = 'attachment; filename=%s.pdf' % id
response.write(pdf)
#< (-4,0), (-3,0), (-2,0), (0,0)
response


# -----------------
# imports
# -----------------
#< (0,7), (3,0)
import module_not_exists

#< (-3,7), (0,0)
module_not_exists


#< ('rename1', 1,0), (0,24), (3,0), (6,17), ('rename2', 4,5), (10,17), (13,17)
from import_tree import rename1

#< (0,8), ('rename1',3,0), ('rename2',4,20), ('rename2',6,0), (3,32), (7,32), (4,0)
rename1.abc

#< (-3,8), ('rename1', 3,0), ('rename2', 4,20), ('rename2', 6,0), (0,32), (4,32), (1,0)
from import_tree.rename1 import abc
abc

#< 20 ('rename1', 1,0), ('rename2', 4,5), (-10,24), (-7,0), (-4,17), (0,17), (3,17)
from import_tree.rename1 import abc

#< (0, 32),
from import_tree.rename1 import not_existing

# shouldn't work
#< 
from not_existing import *

# -----------------
# classes
# -----------------

class TestMethods(object):
    #< 8 (0,8), (2,13)
    def a_method(self):
        #< 13 (-2,8), (0,13)
        self.a_method()
        #< 13 (2,8), (0,13), (3,13)
        self.b_method()

    def b_method(self):
        self.b_method


class TestClassVar(object):
    #< 4 (0,4), (5,13), (7,21)
    class_v = 1
    def a(self):
        class_v = 1

        #< (-5,4), (0,13), (2,21)
        self.class_v
        #< (-7,4), (-2,13), (0,21)
        TestClassVar.class_v
        #< (0,8), (-7, 8)
        class_v

class TestInstanceVar():
    def a(self):
        #< 13 (4,13), (0,13)
        self._instance_var = 3

    def b(self):
        #< (-4,13), (0,13)
        self._instance_var


class NestedClass():
    def __getattr__(self, name):
        return self

# Shouldn't find a definition, because there's no name defined (used ``getattr``).

#< (0, 14),
NestedClass().instance


# -----------------
# inheritance
# -----------------
class Super(object):
    #< 4 (0,4), (23,18), (25,13)
    base_class = 1
    #< 4 (0,4),
    class_var = 1

    #< 8 (0,8),
    def base_method(self):
        #< 13 (0,13), (20,13)
        self.base_var = 1
        #< 13 (0,13), (24,13), (29,13)
        self.instance_var = 1

    #< 8 (0,8),
    def just_a_method(self): pass


#< 20 (0,16), (-18,6)
class TestClass(Super):
    #< 4 (0,4),
    class_var = 1

    def x_method(self):

        #< (0,18), (2,13), (-23,4)
        TestClass.base_class
        #< (-2,18), (0,13), (-25,4)
        self.base_class
        #< (-20,13), (0,13)
        self.base_var
        #< 
        TestClass.base_var


        #< 13 (5,13), (0,13)
        self.instance_var = 3

    #< 9 (0,8), 
    def just_a_method(self):
        #< (-5,13), (0,13), (-29,13)
        self.instance_var


# -----------------
# properties
# -----------------
class TestProperty:

    @property
    #< 10 (0,8), (5,13)
    def prop(self):
        return 1

    def a(self):
        #< 13 (-5,8), (0,13)
        self.prop

    @property
    #< 13 (0,8), (4,5)
    def rw_prop(self):
        return self._rw_prop

    #< 8 (-4,8), (0,5)
    @rw_prop.setter
    #< 8 (0,8), (5,13)
    def rw_prop(self, value):
        self._rw_prop = value

    def b(self):
        #< 13 (-5,8), (0,13)
        self.rw_prop

# -----------------
# *args, **kwargs
# -----------------
#< 11 (1,11), (0,8)
def f(**kwargs):
    return kwargs


# -----------------
# No result
# -----------------
if isinstance(j, int):
    #< 
    j
