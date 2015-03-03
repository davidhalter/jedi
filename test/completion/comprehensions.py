# -----------------
# list comprehensions
# -----------------

# basics:

a = ['' for a in [1]]
#? str()
a[0]
#? ['insert']
a.insert

a = [a for a in [1]]
#? int()
a[0]

y = 1.0
# Should not leak.
[y for y in [3]]
#? float()
y

a = [a for a in (1, 2)]
#? int()
a[0]

a = [a for a,b in [(1,'')]]
#? int()
a[0]

arr = [1,'']
a = [a for a in arr]
#? int() str()
a[0]

a = [a if 1.0 else '' for a in [1] if [1.0]]
#? int() str()
a[0]

# name resolve should be correct
left, right = 'a', 'b'
left, right = [x for x in (left, right)]
#? str()
left

# with a dict literal
#? str()
[a for a in {1:'x'}][0]

##? str()
{a-1:b for a,b in {1:'a', 3:1.0}.items()}[0]

# list comprehensions should also work in combination with functions
def listen(arg):
    for x in arg:
        #? str()
        x

listen(['' for x in [1]])
#? str
([str for x in []])[0]


# -----------------
# nested list comprehensions
# -----------------

b = [a for arr in [[1]] for a in arr]
#? int()
b[0]

b = [a for arr in [[1]] if '' for a in arr if '']
#? int()
b[0]

b = [b for arr in [[[1.0]]] for a in arr for b in a]
#? float()
b[0]

# jedi issue #26
#? list()
a = [[int(v) for v in line.strip().split() if v] for line in ["123", "123", "123"] if line]
#? list()
a[0]
#? int()
a[0][0]

# -----------------
# generator comprehensions
# -----------------

left, right = (i for i in (1, ''))

#? int()
left

gen = (i for i in (1,))

#? int()
next(gen)
#?
gen[0]

gen = (a for arr in [[1.0]] for a in arr)
#? float()
next(gen)

#? int()
(i for i in (1,)).send()

# issues with different formats
left, right = (i for i in
                       ('1', '2'))
#? str()
left

# -----------------
# name resolution in comprehensions.
# -----------------

def x():
    """Should not try to resolve to the if hio, which was a bug."""
    #? 22
    [a for a in h if hio]
    if hio: pass
