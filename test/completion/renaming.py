"""
Renaming tests. This means search for related names.
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




response = 5
#< 0 (0,0), (1,0), (2,0), (4,0)
response = HttpResponse(mimetype='application/pdf')
response['Content-Disposition'] = 'attachment; filename=%s.pdf' % id
response.write(pdf)
#< (-4,0), (-3,0), (-2,0), (0,0)
response
