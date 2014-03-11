"""
Test Jedi's operation understanding. Jedi should understand simple additions,
multiplications, etc.
"""
# -----------------
# numbers
# -----------------
x = [1, 'a', 1.0]

#? int() str() float()
x[12]

#? float()
x[1 + 1]

index = 0 + 1

#? str()
x[index]


def calculate(number):
    return number + constant

constant = 1

#? float()
x[calculate(1)]

def calculate(number):
    return number + constant

# -----------------
# strings
# -----------------

x = 'upp' + 'e'

#? str.upper
getattr(str, x + 'r')

# -----------------
# assignments
# -----------------

x = [1, 'a', 1.0]

i = 0
i += 1
i += 1
#? float()
x[i]

i = 1
i += 1
i -= 3
i += 1
#? int()
x[i]

# -----------------
# for flow assignments
# -----------------

class FooBar(object):
    fuu = 0.1
    raboof = 'fourtytwo'

# targets should be working
target = ''
for char in ['f', 'u', 'u']:
    target += char
#? float()
getattr(FooBar, target)

# github #24
target = u''
for char in reversed(['f', 'o', 'o', 'b', 'a', 'r']):
    target += char

#? str()
getattr(FooBar, target)
