""" Test docstrings in functions and classes, which are used to infer types """

def f(a, b):
    """ asdfasdf
    :param a: blablabla
    :type a: str
    :rtype: dict
    """
    #? str()
    a
    #? 
    b

#? dict()
f()

def g(a, b):
    """ asdfasdf
    Arguments:
        a (str): blablabla

    Returns: list
        Blah blah.
    """
    #? str()
    a
    #? 
    b

#? list()
g()

def e(a, b):
    """ asdfasdf
    @type a: str
    @param a: blablabla
    @rtype: list
    """
    #? str()
    a
    #?
    b

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
