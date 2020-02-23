# -------------------------------------------------- in-module-1
#? 11 text {'new_name': 'a'}
test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 11 text {'new_name': 'a'}
def a(b):
    return 30 + b


test(100, (a(b), c) + 1)
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
def ab(x):
    return x + 1 * 2


def f(x):
#? 11 text {'new_name': 'ab'}
    return ab(x)
# -------------------------------------------------- in-function-with-dec
@classmethod
def f(x):
#? 11 text {'new_name': 'ab'}
    return x + 1 * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def ab(x):
    return x + 1 * 2


@classmethod
def f(x):
#? 11 text {'new_name': 'ab'}
    return ab(x)
# -------------------------------------------------- in-method-1
class X:
    def z(self): pass

    def f(x, b):
        #? 11 text {'new_name': 'ab'}
        return x + b * 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
class X:
    def z(self): pass

    def ab(x, b):
        return x + b * 2

    def f(x, b):
        #? 11 text {'new_name': 'ab'}
        return x.ab(b)
# -------------------------------------------------- in-classmethod-1
class X:
    @classmethod
    def f(x):
        #? 16 text {'new_name': 'ab'}
        return 25
# ++++++++++++++++++++++++++++++++++++++++++++++++++
class X:
    @classmethod
    def ab():
        return 25

    @classmethod
    def f(x):
        #? 16 text {'new_name': 'ab'}
        return x.ab()
# -------------------------------------------------- in-staticmethod-1
class X(int):
    @staticmethod
    def f(x):
        #? 16 text {'new_name': 'ab'}
        return 25 | 3
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def ab():
    return 25 | 3

class X(int):
    @staticmethod
    def f(x):
        #? 16 text {'new_name': 'ab'}
        return ab()
# -------------------------------------------------- in-class-1
class Ya():
    a = 3
    #? 11 text {'new_name': 'f'}
    c = a + 2
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def f(a):
    return a + 2


class Ya():
    a = 3
    #? 11 text {'new_name': 'f'}
    c = f(a)
