"""
Tests for all async use cases.

Currently we're not supporting completion of them, but they should at least not
raise errors or return extremely strange results.
"""

async def x():
    argh = await x()
    #? 
    argh
    return 2

#? int()
x()

a = await x()
#?
a


async def x2():
    async with open('asdf') as f:
        #? ['readlines']
        f.readlines

class A():
    @staticmethod
    async def b(c=1, d=2):
        return 1

#! 9 ['def b']
await A.b()

#! 11 ['param d=2']
await A.b(d=3)
