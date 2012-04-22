
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
