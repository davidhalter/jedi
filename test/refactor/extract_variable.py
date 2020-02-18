# -------------------------------------------------- simple-1
def test():
    #? 35 text {'new_name': 'a'}
    return test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 35 text {'new_name': 'a'}
    a = (30 + b, c) + 1
    return test(100, a)
# -------------------------------------------------- simple-2
def test():
    #? 25 text {'new_name': 'a'}
    return test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 25 text {'new_name': 'a'}
    a = 30 + b
    return test(100, (a, c) + 1)
# -------------------------------------------------- simple-3
#? 13 text {'new_name': 'zzx.x'}
test(100, {1  |1: 2 + 3})
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 13 text {'new_name': 'zzx.x'}
zzx.x = 1  |1
test(100, {zzx.x: 2 + 3})
# -------------------------------------------------- multiline-1
def test():
    #? 30 text {'new_name': 'x'}
    return test(1, (30 + b, c) 
                            + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 30 text {'new_name': 'x'}
    x = (30 + b, c) 
                                + 1
    return test(1, x)
# -------------------------------------------------- multiline-2
def test():
    #? 25 text {'new_name': 'x'}
    return test(1, (30 + b, c) 
                            + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 25 text {'new_name': 'x'}
    x = 30 + b
    return test(1, (x, c) 
                            + 1)
# -------------------------------------------------- for-param-error-1
#? 10 error {'new_name': 'x'}
def test(p1):
    return
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot extract a definition of a name
# -------------------------------------------------- for-param-error-2
#? 12 error {'new_name': 'x'}
def test(p1= 3):
    return
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot extract a param
# -------------------------------------------------- for-param-1
#? 12 text {'new_name': 'x'}
def test(p1=20):
    return
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 12 text {'new_name': 'x'}
x = 20
def test(p1=x):
    return
# -------------------------------------------------- for-something
#? 12 text {'new_name': 'x'}
def test(p1=20):
    return
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 12 text {'new_name': 'x'}
x = 20
def test(p1=x):
    return
# -------------------------------------------------- class-inheritance-1
#? 12 text {'new_name': 'x'}
class Foo(foo.Bar):
    pass
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 12 text {'new_name': 'x'}
x = foo.Bar
class Foo(x):
    pass
# -------------------------------------------------- class-inheritance-2
#? 16 text {'new_name': 'x'}
class Foo(foo.Bar):
    pass
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 16 text {'new_name': 'x'}
x = foo.Bar
class Foo(x):
    pass
