# -------------------------------------------------- in-module-1
#? 11 text {'new_name': 'a'}
test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 11 text {'new_name': 'a'}
def a():
    return 30 + b


test(100, (a(), c) + 1)
# -------------------------------------------------- in-module-2
#? 0 text {'new_name': 'ab'}
100 + 1 * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 0 text {'new_name': 'ab'}
def ab():
    return 100 + 1 * 2


ab()
# -------------------------------------------------- in-function-1
def f(x):
#? 11 text {'new_name': 'ab'}
    return x + 1 * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def ab():
    return x + 1 * 2


def f(x):
#? 11 text {'new_name': 'ab'}
    return ab()
# -------------------------------------------------- in-function-with-dec
@classmethod
def f(x):
#? 11 text {'new_name': 'ab'}
    return x + 1 * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def ab():
    return x + 1 * 2


@classmethod
def f(x):
#? 11 text {'new_name': 'ab'}
    return ab()
# -------------------------------------------------- in-method-1
class X:
    def z(self): pass

    def f(x):
        #? 11 text {'new_name': 'ab'}
        return x + 1 * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
class X:
    def z(self): pass

    def ab():
        return x + 1 * 2

    def f(x):
        #? 11 text {'new_name': 'ab'}
        return ab()
