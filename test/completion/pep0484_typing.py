# python >= 3.2
import typing
class B:
    pass

def we_can_has_sequence(
        p: typing.Sequence[int],
        q: typing.Sequence[B],
        r: "typing.Sequence[int]",
        s: typing.Sequence["int"],
        t: typing.MutableSequence[dict],
        u: typing.List[float]):
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

def iterators(
        ps: typing.Iterable[int],
        qs: typing.Iterator[str],
        rs: typing.Sequence["ForwardReference"],
        ts: typing.AbstractSet["float"]):
    for p in ps:
        #? int()
        p
    #?
    next(ps)
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

def sets(
        p: typing.AbstractSet[int],
        q: typing.MutableSet[float]):
    #? []
    p.a
    #? ["add"]
    q.a

def tuple(
        p: typing.Tuple[int],
        q: typing.Tuple[int, str, float],
        r: typing.Tuple[B, ...]):
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
    ##? B()  --- TODO fix support for arbitrary length
    r[1]
    #? B()
    r[2]
    #? B()
    r[10000]
    i, s, f = q
    #? int()
    i
    ##? str()  --- TODO fix support for tuple assignment
    s
    ##? float()  --- TODO fix support for tuple assignment
    f

class Key:
    pass

class Value:
    pass

def mapping(
        p: typing.Mapping[Key, Value],
        q: typing.MutableMapping[Key, Value],
        d: typing.Dict[Key, Value],
        r: typing.KeysView[Key],
        s: typing.ValuesView[Value],
        t: typing.ItemsView[Key, Value]):
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
        ##? Value()  --- TODO fix support for tuple assignment
        value
    for key, value in p.items():
        #? Key()
        key
        ##? Value()  --- TODO fix support for tuple assignment
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
        ##? Value()  --- TODO fix support for tuple assignment
        value

class ForwardReference:
    pass
