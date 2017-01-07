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
