# normal
a = ""
a = 1

#? ['real']
a.real
#? []
a.upper
#? []
a.append


a = list

# function stuff
def a(a=3):
    #? ['real']
    a.real
    #? []
    a.upper
    #? []
    a.func
    return a

#? ['real']
a(2).real
#? []
a(2).upper
#? []
a(2).func

# class stuff
class A(object):
    a = ""
    a = 3
    #? ['real']
    a.real
    #? []
    a.upper
    #? []
    a.append
    a = list
    def __init__(self):
        self.b = ""
        self.b = 3
        #? ['real']
        self.b.real
        #? []
        self.b.upper
        #? []
        self.b.append

        self.b = list

    def before(self):
        self.a = 1
        #? ['real']
        self.a.real
        #? ['upper']
        self.a.upper

    def after(self):
        self.a = ''

##? ['real']
A.a.real
##? []
A.a.upper
##? []
A.a.append

