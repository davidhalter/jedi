"""
Renaming tests. This means search for related names.
I always leave a little bit of space to add room for additions, because the
results always contain position informations.
"""
#< 4 (7,4), (10,0), (12,0)
def abc(): pass

#< 0 (7,4), (10,0), (12,0)
abc.d.a.bsaasd.abc.d

abc







abc = 

#< (20,0), (23,0)
abc



Abc = 3

#< 6 (30,6), (32,4), (35,8), (47,0)
class Abc():
    #< (30,6), (32,4), (35,8), (47,0)
    Abc

    def Abc(self):
        Abc; self.c = 3

    #< 17 (38,16), (40,8)
    def a(self, Abc):
        #< 10 (38,16), (40,8)
        Abc

    #< 19 (43,18), (45,8)
    def self_test(self):
        #< 12 (43,18), (45,8)
        self.b

Abc.d.Abc






#< 4 (55,4), (59,1)
def blub():


#< (55,4), (59,1)
@blub
def a(): pass



#< (65,7), (68,0)
import module_not_exists

#< (65,7), (68,0)
module_not_exists





#< (1,0), (75,24), (78,0), (81,17), (4,5), (85,17), (88,17)
from import_tree import rename1

#< (78,8), (3,0), (4,20), (6,0), (81,32), (85,32), (82,0)
rename1.abc

#< (78,8), (3,0), (4,20), (6,0), (81,32), (85,32), (82,0)
from import_tree.rename1 import abc
abc

#< 20 (1,0), (4,5), (75,24), (78,0), (81,17), (85,17), (88,17)
from import_tree.rename1 import abc

#< (88, 32),
from import_tree.rename1 import not_existing




response = 5
#< 0 (95, 0), (96, 0), (97, 0), (99, 0)
response = HttpResponse(mimetype='application/pdf')
response['Content-Disposition'] = 'attachment; filename=%s.pdf' % id
response.write(pdf)
#< (95, 0), (96, 0), (97, 0), (99, 0)
response
