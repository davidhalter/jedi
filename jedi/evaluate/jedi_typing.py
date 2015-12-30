"""
This module is not intended to be used in jedi, rather it will be fed to the
jedi-parser to replace classes in the typing module
"""

from collections import abc


def factory(typing_name, indextype):
    class Sequence(abc.Sequence):
        def __getitem__(self) -> indextype:
            pass

    class MutableSequence(Sequence, abc.MutableSequence):
            pass

    class List(MutableSequence, list):
            pass

    dct = {
        "Sequence": Sequence,
        "MutableSequence": MutableSequence,
        "List": List,
    }
    return dct[typing_name]
