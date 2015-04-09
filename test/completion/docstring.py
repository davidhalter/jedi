""" Test docstrings in functions and classes, which are used to infer types """

# -----------------
# sphinx style
# -----------------
def sphinxy(a, b, c, d, x):
    """ asdfasdf
    :param a: blablabla
    :type a: str
    :type b: (str, int)
    :type c: random.Random
    :type d: :class:`random.Random`
    :param str x: blablabla
    :rtype: dict
    """
    #? str()
    a
    #? str()
    b[0]
    #? int()
    b[1]
    #? ['seed']
    c.seed
    #? ['seed']
    d.seed
    #? ['lower']
    x.lower

#? dict()
sphinxy()

# wrong declarations
def sphinxy2(a, b, x):
    """
    :param a: Forgot type declaration
    :type a:
    :param b: Just something
    :type b: ``
    :param x: Just something without type
    :rtype:
    """
    #? 
    a
    #? 
    b
    #?
    x

#? 
sphinxy2()

# local classes -> github #370
class ProgramNode():
    pass

def local_classes(node, node2):
    """
    :type node: ProgramNode
    ... and the class definition after this func definition:
    :type node2: ProgramNode2
    """
    #? ProgramNode()
    node
    #? ProgramNode2()
    node2

class ProgramNode2():
    pass


def list_with_non_imports(lst):
    """
    Should be able to work with tuples and lists and still import stuff.

    :type lst: (random.Random, [collections.defaultdict, ...])
    """
    #? ['seed']
    lst[0].seed

    import collections as col
    # use some weird index
    #? col.defaultdict()
    lst[1][10]


def two_dots(a):
    """
    :type a: json.decoder.JSONDecoder
    """
    #? ['raw_decode']
    a.raw_decode


# sphinx returns
def return_module_object():
    """
    :rtype: :class:`random.Random`
    """

#? ['seed']
return_module_object().seed


# -----------------
# epydoc style
# -----------------
def epydoc(a, b):
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
epydoc()


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

#? str() int()
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
