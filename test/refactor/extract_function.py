# -------------------------------------------------- in-module-1
glob = 3
#? 11 text {'new_name': 'a'}
test(100, (glob.a + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
glob = 3
#? 11 text {'new_name': 'a'}
def a(b):
    return glob.a + b


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
# -------------------------------------------------- in-method-2
glob1 = 1
class X:
    def g(self): pass

    def f(self, b, c):
        #? 11 text {'new_name': 'ab'}
        return self.g() or self.f(b) ^ glob1 & b
# ++++++++++++++++++++++++++++++++++++++++++++++++++
glob1 = 1
class X:
    def g(self): pass

    def ab(self, b):
        return self.g() or self.f(b) ^ glob1 & b

    def f(self, b, c):
        #? 11 text {'new_name': 'ab'}
        return self.ab(b)
# -------------------------------------------------- in-method-order
class X:
    def f(self, b, c):
        #? 18 text {'new_name': 'b'}
        return b | self.a
# ++++++++++++++++++++++++++++++++++++++++++++++++++
class X:
    def b(self, b):
        return b | self.a

    def f(self, b, c):
        #? 18 text {'new_name': 'b'}
        return self.b(b)
# -------------------------------------------------- in-classmethod-1
class X:
    @classmethod
    def f(x):
        #? 16 text {'new_name': 'ab'}
        return 25
# ++++++++++++++++++++++++++++++++++++++++++++++++++
class X:
    @classmethod
    def ab(x):
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
# -------------------------------------------------- in-closure
def x(z):
    def y(x):
        #? 15 text {'new_name': 'f'}
        return -x * z
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def f(x, z):
    return -x * z


def x(z):
    def y(x):
        #? 15 text {'new_name': 'f'}
        return f(x, z)
# -------------------------------------------------- with-range-1
#? 0 text {'new_name': 'a', 'until_line': 4}
v1 = 3
v2 = 2
x = test(v1 + v2 * v3)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 0 text {'new_name': 'a', 'until_line': 4}
def a(test, v3):
    v1 = 3
    v2 = 2
    x = test(v1 + v2 * v3)
    return x


x = a(test, v3)
# -------------------------------------------------- with-range-2
#? 2 text {'new_name': 'a', 'until_line': 6, 'until_column': 4}
#foo
v1 = 3
v2 = 2
x, y = test(v1 + v2 * v3)
#raaaa
y
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#? 2 text {'new_name': 'a', 'until_line': 6, 'until_column': 4}
def a(test, v3):
    #foo
    v1 = 3
    v2 = 2
    x, y = test(v1 + v2 * v3)
    #raaaa
    return y


y = a(test, v3)
y
# -------------------------------------------------- with-range-3
#foo
#? 2 text {'new_name': 'a', 'until_line': 5, 'until_column': 4}
v1 = 3
v2 = 2
x, y = test(v1 + v2 * v3)
#raaaa
y
# ++++++++++++++++++++++++++++++++++++++++++++++++++
#foo
#? 2 text {'new_name': 'a', 'until_line': 5, 'until_column': 4}
def a(test, v3):
    v1 = 3
    v2 = 2
    x, y = test(v1 + v2 * v3)
    return y


y = a(test, v3)
#raaaa
y
# -------------------------------------------------- with-range-func-1
import os
# comment1
@dec
# comment2
def x(v1):
    #foo
    #? 2 text {'new_name': 'a', 'until_line': 9, 'until_column': 5}
    v2 = 2
    if 1:
        x, y = os.listdir(v1 + v2 * v3)
    #bar
    return x, y
# ++++++++++++++++++++++++++++++++++++++++++++++++++
import os
# comment1
def a(v1, v2, v3):
    v2 = 2
    if 1:
        x, y = os.listdir(v1 + v2 * v3)
    return x, y


@dec
# comment2
def x(v1):
    #foo
    #? 2 text {'new_name': 'a', 'until_line': 9, 'until_column': 5}
    x, y = a(v1, v2, v3)
    #bar
    return x, y
# -------------------------------------------------- with-range-func-2
import os
# comment1
@dec
# comment2
def x(v1):
    #? 2 text {'new_name': 'a', 'until_line': 11, 'until_column': 0}
    #foo
    v2 = 2
    if 1:
        x, y = os.listdir(v1 + v2 * v3)
    #bar
    return y
x
# ++++++++++++++++++++++++++++++++++++++++++++++++++
import os
# comment1
def a(v1, v2, v3):
    #foo
    v2 = 2
    if 1:
        x, y = os.listdir(v1 + v2 * v3)
    #bar
    return y


@dec
# comment2
def x(v1):
    #? 2 text {'new_name': 'a', 'until_line': 11, 'until_column': 0}
    y = a(v1, v2, v3)
    return y
x
