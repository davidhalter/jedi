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
x support for type hint comments `# type: (int, str) -> int`. See comment from
    Guido https://github.com/davidhalter/jedi/issues/662
"""

from itertools import chain

from jedi.parser import Parser, load_grammar, ParseError
from jedi.evaluate.cache import memoize_default
from jedi.evaluate.compiled import CompiledObject
from jedi import debug


def _evaluate_for_annotation(evaluator, annotation):
    if annotation is not None:
        definitions = set()
        for definition in evaluator.eval_element(annotation):
            if (isinstance(definition, CompiledObject) and
                    isinstance(definition.obj, str)):
                try:
                    p = Parser(load_grammar(), definition.obj, start='eval_input')
                    element = p.get_parsed_node()
                except ParseError:
                    debug.warning('Annotation not parsed: %s' % definition.obj)
                else:
                    module = annotation.get_parent_until()
                    p.position_modifier.line = module.end_pos[0]
                    element.parent = module
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
