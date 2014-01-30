"""
Test Jedi's operation understanding. Jedi should understand simple additions,
multiplications, etc.
"""
x = [1, '', 'a', 1.0]

#? int() str() float()
x[12]

#? str()
x[1 + 1]

index = 0 + 1

#? str()
x[index]


def calculate(number):
    return number + constant

constant = 1

#? float()
x[calculate(2)]
