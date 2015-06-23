import random

if random.choice([0, 1]):
    x = ''
else:
    x = 1
if random.choice([0, 1]):
    y = ''
else:
    y = 1

# A simple test
if x != 1:
    x.upper()
else:
    #! 2 attribute-error
    x.upper()
    pass

# This operation is wrong, because the types could be different.
#! 6 type-error-operation
z = x + y
# However, here we have correct types.
if type(x) == type(y):
    z = x + y
