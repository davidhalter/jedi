""" Pep-0484 type hinting """

# python >= 3.2


class A():
    pass


def function_parameters(a: A, b, c: str, d: int=4):
    #? A()
    a
    #?
    b
    #? str()
    c
    #? int()
    d


def return_unspecified():
    pass

#?
return_unspecified()


def return_none() -> None:
    """
    Return type None means the same as no return type as far as jedi
    is concerned
    """
    pass

#?
return_none()


def return_str() -> str:
    pass

#? str()
return_str()


def return_custom_class() -> A:
    pass

#? A()
return_custom_class()


def return_annotation_and_docstring() -> str:
    """
    :rtype: int
    """
    pass

#? str() int()
return_annotation_and_docstring()


def return_annotation_and_docstring_different() -> str:
    """
    :rtype: str
    """
    pass

#? str()
return_annotation_and_docstring_different()
