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

class FooBar(object):
    muahaha = 3.0
    raboof = 'fourtytwo'

x = 'mua' + 'ha'

#? float()
getattr(FooBar, x + 'ha')


# github #24
target = u''
for char in reversed(['f', 'o', 'o', 'b', 'a', 'r']):
    target += char

answer = getattr(FooBar, target)
##? str()
answer

# -----------------
# assignments
# -----------------

x = [1, 'a', 1.0]

i = 0
i += 1
i += 1
#? float()
x[i]
