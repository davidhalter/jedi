def whatever(code):
    if '.' in code:
        another(code[:code.index('.') - 1] + '!')
    else:
        another(code + '.')


def another(code2):
    call(ret(code2 + 'haha'))

whatever('1.23')
whatever('1,23')


def ret2(code4):
    if 1:
        if 2:
            return code4 + 'i'
        else:
            return code4 + 'k'
    else:
        if 2:
            return code4 + 'l'
        else:
            return code4 + 'h'


def ret(code5):
    if 2:
        return ret2(code5 + 'r')
    else:
        return ret2(code5 + 'k')


def call(code3):
    code3 = ret(ret('1')) + ret(code3)
    code3.partition
