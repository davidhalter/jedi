# -----------------
# for loops
# -----------------

for a in [1,2]:
    #? ['real']
    a.real

for a1 in 1,"":
    #? ['real']
    a1.real
    #? ['upper']
    a1.upper

for a3, b3 in (1,""), (1,""), (1,""):
    #? ['real']
    a3.real
    #? []
    a3.upper
    #? []
    b3.real
    #? ['upper']
    b3.upper

# -----------------
# with statements
# -----------------

with open('') as f:
    #? ['closed']
    f.closed

with open('') as f1, open('') as f2:
    #? ['closed']
    f1.closed
    #? ['closed']
    f2.closed


# -----------------
# global vars
# -----------------

def global_define():
    global glob
    glob = 3

#? ['real']
glob.real
