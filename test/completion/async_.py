"""
Tests for all async use cases.

Currently we're not supporting completion of them, but they should at least not
raise errors or return strange results.
"""


async def x():
    await 3

#?
x()

a = await x()
#?
a


