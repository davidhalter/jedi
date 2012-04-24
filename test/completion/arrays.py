# -----------------
# basic array lookups
# -----------------

#? ['imag']
[1,""][0].imag
#? []
[1,""][1].imag

a = list()
#? ['append']
[a][0].append

#? ['append']
[[a]][0][100].append


# -----------------
# tuple assignments
# -----------------
a1, b1 = (1, "")
#? ['real']
a1.real
#? ['lower']
b1.lower
#? []
b1.real

(a2, b2) = (1, "")
#? ['imag']
a2.imag
#? ['upper']
b2.upper

# -----------------
# subtuple assignment
# -----------------
(a3, (b3, c3)) = (1, ("", list))
##? ['append']
c3.append
#? []
c3.upper
#? []
c3.real

a4, (b4, c4) = (1, ("", list))
#? ['append']
c4.append
#? []
c4.upper
#? []
c4.real
#? ['real']
a4.real
#? ['upper']
b4.upper


# -----------------
# unnessecary braces
# -----------------
u, v = 1, ""
#? ['real']
u.real
#? []
u.upper
