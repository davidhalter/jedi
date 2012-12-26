""" Test docstrings in functions and classes, which are used to infer types """

def f(a, b):
    """ asdfasdf
    :param a: blablabla
    :type a: str
    """
    #? str()
    a
    #? 
    b

def g(a, b):
    """ asdfasdf
    Arguments:
        a (str): blablabla
    """
    #? str()
    a
    #? 
    b
