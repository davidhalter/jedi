"""
Test the typing library, with docstrings. This is needed since annotations
are not supported in python 2.7 else then annotating by comment (and this is
still TODO at 2016-01-23)
"""
# There's no Python 2.6 typing module.
# python >= 2.7
import typing
class B:
    pass

def we_can_has_sequence(p, q, r, s, t, u):
    """
    :type p: typing.Sequence[int]
    :type q: typing.Sequence[B]
    :type r: typing.Sequence[int]
    :type s: typing.Sequence["int"]
    :type t: typing.MutableSequence[dict]
    :type u: typing.List[float]
    """
    #? ["count"]
    p.c
    #? int()
    p[1]
    #? ["count"]
    q.c
    #? B()
    q[1]
    #? ["count"]
    r.c
    #? int()
    r[1]
    #? ["count"]
    s.c
    #? int()
    s[1]
    #? []
    s.a
    #? ["append"]
    t.a
    #? dict()
    t[1]
    #? ["append"]
    u.a
    #? float()
    u[1]

def iterators(ps, qs, rs, ts):
    """
    :type ps: typing.Iterable[int]
    :type qs: typing.Iterator[str]
    :type rs: typing.Sequence["ForwardReference"]
    :type ts: typing.AbstractSet["float"]
    """
    for p in ps:
        #? int()
        p
    #?
    next(ps)
    a, b = ps
    #? int()
    a
    ##? int()  --- TODO fix support for tuple assignment
    # https://github.com/davidhalter/jedi/pull/663#issuecomment-172317854
    # test below is just to make sure that in case it gets fixed by accident
    # these tests will be fixed as well the way they should be
    #?
    b

    for q in qs:
        #? str()
        q
    #? str()
    next(qs)
    for r in rs:
        #? ForwardReference()
        r
    #?
    next(rs)
    for t in ts:
        #? float()
        t

def sets(p, q):
    """
    :type p: typing.AbstractSet[int]
    :type q: typing.MutableSet[float]
    """
    #? []
    p.a
    #? ["add"]
    q.a

def tuple(p, q, r):
    """
    :type p: typing.Tuple[int]
    :type q: typing.Tuple[int, str, float]
    :type r: typing.Tuple[B, ...]
    """
    #? int()
    p[0]
    #? int()
    q[0]
    #? str()
    q[1]
    #? float()
    q[2]
    #? B()
    r[0]
    #? B()
    r[1]
    #? B()
    r[2]
    #? B()
    r[10000]
    i, s, f = q
    #? int()
    i
    ##? str()  --- TODO fix support for tuple assignment
    # https://github.com/davidhalter/jedi/pull/663#issuecomment-172317854
    #?
    s
    ##? float()  --- TODO fix support for tuple assignment
    # https://github.com/davidhalter/jedi/pull/663#issuecomment-172317854
    #?
    f

class Key:
    pass

class Value:
    pass

def mapping(p, q, d, r, s, t):
    """
    :type p: typing.Mapping[Key, Value]
    :type q: typing.MutableMapping[Key, Value]
    :type d: typing.Dict[Key, Value]
    :type r: typing.KeysView[Key]
    :type s: typing.ValuesView[Value]
    :type t: typing.ItemsView[Key, Value]
    """
    #? []
    p.setd
    #? ["setdefault"]
    q.setd
    #? ["setdefault"]
    d.setd
    #? Value()
    p[1]
    for key in p:
        #? Key()
        key
    for key in p.keys():
        #? Key()
        key
    for value in p.values():
        #? Value()
        value
    for item in p.items():
        #? Key()
        item[0]
        #? Value()
        item[1]
        (key, value) = item
        #? Key()
        key
        #? Value()
        value
    for key, value in p.items():
        #? Key()
        key
        #? Value()
        value
    for key in r:
        #? Key()
        key
    for value in s:
        #? Value()
        value
    for key, value in t:
        #? Key()
        key
        #? Value()
        value

def union(p, q, r, s, t):
    """
    :type p: typing.Union[int]
    :type q: typing.Union[int, int]
    :type r: typing.Union[int, str, "int"]
    :type s: typing.Union[int, typing.Union[str, "typing.Union['float', 'dict']"]]
    :type t: typing.Union[int, None]
    """
    #? int()
    p
    #? int()
    q
    #? int() str()
    r
    #? int() str() float() dict()
    s
    #? int()
    t

def optional(p):
    """
    :type p: typing.Optional[int]
    Optional does not do anything special. However it should be recognised
    as being of that type. Jedi doesn't do anything with the extra into that
    it can be None as well
    """
    #? int()
    p

class ForwardReference:
    pass

class TestDict(typing.Dict[str, int]):
    def setdud(self):
        pass

def testdict(x):
    """
    :type x: TestDict
    """
    #? ["setdud", "setdefault"]
    x.setd
    for key in x.keys():
        #? str()
        key
    for value in x.values():
        #? int()
        value

x = TestDict()
#? ["setdud", "setdefault"]
x.setd
for key in x.keys():
    #? str()
    key
for value in x.values():
    #? int()
    value
# python >= 3.2
"""
docstrings have some auto-import, annotations can use all of Python's
import logic
"""
import typing as t
def union2(x: t.Union[int, str]):
    #? int() str()
    x

from typing import Union
def union3(x: Union[int, str]):
    #? int() str()
    x

from typing import Union as U
def union4(x: U[int, str]):
    #? int() str()
    x
