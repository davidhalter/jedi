"""
This module is not intended to be used in jedi, rather it will be fed to the
jedi-parser to replace classes in the typing module
"""

from collections import abc


def factory(typing_name, indextype):
    class Iterable(abc.Iterable):
        def __iter__(self):
            yield indextype()

    class Iterator(Iterable, abc.Iterator):
        def next(self):
            """ needed for python 2 """
            return self.__next__()

        def __next__(self):
            return indextype()

    class Sequence(Iterable, abc.Sequence):
        def __getitem__(self, index: int):
            return indextype()

    class MutableSequence(Sequence, abc.MutableSequence):
        def __setitem__(self, index: int, value: indextype):
            pass

        def __delitem__(self, index: int, value: indextype):
            pass

    class List(MutableSequence, list):
        pass

    class AbstractSet(Iterable, abc.Set):
        pass

    class MutableSet(AbstractSet, abc.MutableSet):
        def add(item: indextype):
            pass

        def discard(item: indextype):
            pass

    dct = {
        "Sequence": Sequence,
        "MutableSequence": MutableSequence,
        "List": List,
        "Iterable": Iterable,
        "Iterator": Iterator,
        "AbstractSet": AbstractSet,
        "MutableSet": MutableSet,
    }
    return dct[typing_name]
