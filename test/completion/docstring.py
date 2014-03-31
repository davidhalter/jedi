""" Test docstrings in functions and classes, which are used to infer types """

# -----------------
# sphinx style
# -----------------
def f(a, b, c, d):
    """ asdfasdf
    :param a: blablabla
    :type a: str
    :type b: (str, int)
    :type c: threading.Thread
    :type d: :class:`threading.Thread`
    :rtype: dict
    """
    #? str()
    a
    #? str()
    b[0]
    #? int()
    b[1]
    #? ['join']
    c.join
    #? ['join']
    d.join

#? dict()
f()

# wrong declarations
def f(a, b):
    """
    :param a: Forgot type declaration
    :type a:
    :param b: Just something
    :type b: ``
    :rtype: 
    """
    #? 
    a
    #? 
    b

#? 
f()

# local classes -> github #370
class ProgramNode():
    pass

def local_classes(node, node2):
    """
    :type node: ProgramNode
    ... and the class definition after this func definition:
    :type node2: ProgramNode2
    """
    #? ProgramNode
    node
    #? ProgramNode2
    node2

class ProgramNode2():
    pass


def list_with_non_imports(lst):
    """
    Should be able to work with tuples and lists and still import stuff.

    :type lst: (threading.Thread, [collections.defaultdict, ...])
    """
    #? ['start']
    lst[0].start

    import collections as col
    # use some weird index
    #? col.defaultdict()
    lst[1][10]


# sphinx returns
def return_module_object():
    """
    :rtype: :class:`threading.Thread`
    """

#? ['join']
return_module_object().join

# -----------------
# epydoc style
# -----------------
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

class Test(object):
    def __init__(self):
        self.teststr = ""
    """
    # jedi issue #210
    """
    def test(self):
        #? ['teststr']
        self.teststr

# -----------------
# statement docstrings
# -----------------
d = ''
""" bsdf """
#? str()
d.upper()
