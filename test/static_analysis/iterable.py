
a, b = {'asdf': 3, 'b': 'str'}
a

x = [1]
x[0], b = {'a': 1, 'b': '2'}

dct = {3: ''}
for x in dct:
    pass

#! 4 type-error-not-iterable
for x, y in dct:
    pass
