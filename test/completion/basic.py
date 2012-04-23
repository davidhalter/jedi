a1, b1 = (1, "")
#? ['real']
a1.real
#? ['lower']
a1.lower

for a in [1,2]:
    #? ['real']
    a.real

with open('') as f:
    #? ['closed']
    f.closed

with open('') as f1, open('') as f2:
    #? ['closed']
    f1.closed
    #? ['closed']
    f2.closed


def global_define():
    #global glob
    glob = 3

#? ['real']
glob.real
