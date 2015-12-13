"""
PEP 0484 ( https://www.python.org/dev/peps/pep-0484/ ) describes type hints
through function annotations. There is a strong suggestion in this document
that only the type of type hinting defined in PEP0484 should be allowed
as annotations in future python versions.

The (initial / probably incomplete) implementation todo list for pep-0484:
v Function parameter annotations with builtin/custom type classes
v Function returntype annotations with builtin/custom type classes
x Function parameter annotations with strings (forward reference)
x Function return type annotations with strings (forward reference)
x Local variable type hints
x Assigned types: `Url = str\ndef get(url:Url) -> str:`
x Type hints in `with` statements
x Stub files support
x support `@no_type_check` and `@no_type_check_decorator`
"""

from itertools import chain

from jedi.evaluate.cache import memoize_default


@memoize_default(None, evaluator_is_first_arg=True)
def follow_param(evaluator, param):
    annotation = param.annotation()
    if annotation:
        definitions = evaluator.eval_element(annotation)
        return list(chain.from_iterable(
            evaluator.execute(d) for d in definitions))
    else:
        return []
