def generator():
    yield 1

#! 12 type-error-generator
generator()[0]

list(generator())[0]
