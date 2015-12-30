"""
This module is not intended to be used in jedi, rather it will be fed to the
jedi-parser to replace classes in the typing module
"""

from collections import abc


def factory(typing_name, indextype):
    class Sequence(abc.Sequence):
        def __getitem__(self, index: int):
            return indextype()

    class MutableSequence(Sequence, abc.MutableSequence):
        def __setitem__(self, index: int, value: indextype):
            pass

    class List(MutableSequence, list):
            pass

    dct = {
        "Sequence": Sequence,
        "MutableSequence": MutableSequence,
        "List": List,
    }
    return dct[typing_name]
