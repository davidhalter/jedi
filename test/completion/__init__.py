""" needed for some modules to test against packages. """

some_variable = 1


from . import imports
# TODO this is not correct
#? 
imports.relative()
