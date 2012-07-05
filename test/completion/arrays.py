# -----------------
# basic array lookups
# -----------------

#? int()
[1,""][0]
#? str()
[1,""][1]

a = list()
#? list()
[a][0]

#? list()
[[a,a,a]][2][100]

c = [[a,""]]
#? str()
c[0][1]

b = [6,7]

#? int() int()
b[8-7]

#? list()
b[8:]


# -----------------
# tuple assignments
# -----------------
a1, b1 = (1, "")
#? int()
a1
#? str()
b1

(a2, b2) = (1, "")
#? int()
a2
#? str()
b2

# list assignment
[list1, list2] = (1, "")
#? int()
list1
#? str()
list2

[list3, list4] = [1, ""]
#? int()
list3
#? str()
list4

# -----------------
# subtuple assignment
# -----------------
(a3, (b3, c3)) = (1, ("", list))
#? list
c3

a4, (b4, c4) = (1, ("", list))
#? list
c4
#? int()
a4
#? str()
b4


# -----------------
# unnessecary braces
# -----------------
#? int()
(1)
#? int()
((1))
#? int() int()
((1)+1)

u, v = 1, ""
#? int()
u

((u1, v1)) = 1, ""
#? int()
u1
#? int()
(u1)

# -----------------
# should fail (return nothing)
# -----------------
(f, g) = (1,)
#? int()
f
#? []
g.

(f1, g1) = 1
#? []
f1.
#? []
g1.

# -----------------
# dicts
# -----------------
dic2 = {'asdf': 3, 'b': 'str'}
#? int()
dic2['asdf']

# string literal
#? int()
dic2[r'asdf']
#? int()
dic2[r'asdf']
