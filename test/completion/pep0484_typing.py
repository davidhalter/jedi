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

class ForwardReference:
    pass
