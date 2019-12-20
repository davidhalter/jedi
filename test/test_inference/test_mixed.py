import sys
if sys.version_info > (3, 5):
    from typing import Generic, TypeVar, List

import pytest

import jedi


def interpreter(code, namespace, *args, **kwargs):
    return jedi.Interpreter(code, [namespace], *args, **kwargs)


def test_on_code():
    from functools import wraps
    i = interpreter("wraps.__code__", {'wraps': wraps})
    assert i.infer()


@pytest.mark.skipif('sys.version_info < (3,5)')
def test_generics():
    # Used to raise a recursion error
    T = TypeVar('T')

    class Stack(Generic[T]):
        def __init__(self):
            self.items = []  # type: List[T]

        def push(self, item):
            self.items.append(item)

        def pop(self):
            # type: () -> T
            return self.items.pop()

    class StackWrapper():
        def __init__(self):
            self.stack = Stack()
            self.stack.push(1)

    s = StackWrapper()
    print(interpreter('s.stack.pop().', locals()).complete())
