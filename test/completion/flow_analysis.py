def foo(x):
    if 1.0:
        return 1
    else:
        return ''

#? int()
foo(1)


#  Exceptions are not analyzed. So check both if branches
def try_except(x):
    try:
        if 1.0:
            return 1
        else:
            return ''
    except AttributeError:
        return 1.0

#? int() float()
try_except(1)
