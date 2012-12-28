""" Test docstrings in functions and classes, which are used to infer types """

def f(a, b):
    """ asdfasdf
    :param a: blablabla
    :type a: str
    :type b: (str, int)
    :rtype: dict
    """
    #? str()
    a
    #? str()
    b[0]
    #? int()
    b[1]

#? dict()
f()

def e(a, b):
    """ asdfasdf
    @type a: str
    @param a: blablabla
    @type b: (str, int)
    @param b: blablah
    @rtype: list
    """
    #? str()
    a
    #? str()
    b[0]

    #? int()
    b[1]

#? list()
e()


# Returns with param type only
def rparam(a,b):
    """
    @type a: str
    """
    return a

#? str()
rparam()


# Composite types
def composite():
    """
    @rtype: (str, int, dict)
    """

x, y, z = composite()
#? str()
x
#? int()
y
#? dict()
z


# Both docstring and calculated return type
def both():
    """
    @rtype: str
    """
    return 23

#? str(), int()
both()
