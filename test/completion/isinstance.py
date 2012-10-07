if isinstance(i, str):
    #? str()
    i

if isinstance(j, (str, int)):
    #? str() int()
    j

while isinstance(k, (str, int)):
    #? str() int()
    k

if not isinstance(k, (str, int)):
    #? 
    k

while not isinstance(k, (str, int)):
    #? 
    k

assert isinstance(ass, int):
#? int()
ass

assert isinstance(ass, str):
assert not isinstance(ass, int):

if 2:
    #? str()
    ass
