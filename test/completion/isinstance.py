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
