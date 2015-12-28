"""
PEP 0484 ( https://www.python.org/dev/peps/pep-0484/ ) describes type hints
through function annotations. There is a strong suggestion in this document
that only the type of type hinting defined in PEP0484 should be allowed
as annotations in future python versions.

The (initial / probably incomplete) implementation todo list for pep-0484:
v Function parameter annotations with builtin/custom type classes
v Function returntype annotations with builtin/custom type classes
v Function parameter annotations with strings (forward reference)
v Function return type annotations with strings (forward reference)
x Local variable type hints
v Assigned types: `Url = str\ndef get(url:Url) -> str:`
x Type hints in `with` statements
x Stub files support
x support `@no_type_check` and `@no_type_check_decorator`
"""

from itertools import chain
from jedi.parser import Parser, load_grammar
from jedi.parser import tree
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import compiled
from textwrap import dedent


def _evaluate_for_annotation(evaluator, annotation):
    if annotation is not None:
        definitions = set()
        for definition in evaluator.eval_element(annotation):
            if (isinstance(definition, compiled.CompiledObject) and
                    isinstance(definition.obj, str)):
                p = Parser(load_grammar(), definition.obj)
                try:
                    element = p.module.children[0].children[0]
                except (AttributeError, IndexError):
                    continue
                element.parent = annotation.parent
                definitions |= evaluator.eval_element(element)
            else:
                definitions.add(definition)
        return list(chain.from_iterable(
            evaluator.execute(d) for d in definitions))
    else:
        return []


@memoize_default(None, evaluator_is_first_arg=True)
def follow_param(evaluator, param):
    annotation = param.annotation()
    return _evaluate_for_annotation(evaluator, annotation)


@memoize_default(None, evaluator_is_first_arg=True)
def find_return_types(evaluator, func):
    annotation = func.py__annotations__().get("return", None)
    return _evaluate_for_annotation(evaluator, annotation)


# TODO: Memoize
def get_typing_replacement_module():
    """
    The idea is to return our jedi replacement for the PEP-0484 typing module
    as discussed at https://github.com/davidhalter/jedi/issues/663
    """

    code = dedent("""
    from collections import abc

    class MakeSequence:
        def __getitem__(self, indextype):
            class Sequence(abc.Sequence):
                def __getitem__(self) -> indextype:
                    pass
            return Sequence
    """)
    p = Parser(load_grammar(), code)
    return p.module


def get_typing_replacement_class(evaluator, typ):
    if not typ.base.get_parent_until(tree.Module).name.value == "typing":
        return None
    # we assume that any class using [] in a module called
    # "typing" with a name for which we have a replacement
    # should be replaced by that class. This is not 100%
    # airtight but I don't have a better idea to check that it's
    # actually the PEP-0484 typing module and not some other
    typing = get_typing_replacement_module()
    types = evaluator.find_types(typing, "Make" + typ.name.value)
    if not types:
        return None
    else:
        return list(types)[0]
