"""
Renaming tests. This means search for related names.
I always leave a little bit of space to add room for additions, because the
results always contain position informations.
"""
#< 4 (7,4) (10,0) (12,0)
def abc(): pass

#< 0 (7,4) (10,0) (12,0)
abc.d.a.abc.d

abc







abc = 

#< (20,0) (23,0)
abc



Abc = 3

#< 6 (30,6) (32,4) (35,8) (47,0)
class Abc():
    #< (30,6) (32,4) (35,8) (47,0)
    Abc

    def Abc(self):
        Abc; self.c = 3

    #< 17 (38,16) (40,8)
    def a(self, Abc):
        #< 10 (38,16) (40,8)
        Abc

    #< 19 (43,18) (45,8)
    def self_test(self):
        #< 12 (43,18) (45,8)
        self.b

Abc.d.Abc






#< 4 (55,4) (59,1)
def blub():


#< (55,4) (59,1)
@blub
def a(): pass



#< (65,7) (68,0)
import colorama

#< (65,7) (68,0)
colorama

#< 3 
import abc



from import_tree import rename1

#< (78,8) (3,0)
rename1.abc
