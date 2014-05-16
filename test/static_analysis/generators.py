def generator():
    yield 1

#! 11 type-error-generator
generator()[0]

list(generator())[0]
