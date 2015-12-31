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

import itertools

import os
from jedi.parser import \
    Parser, load_grammar, ParseError, ParserWithRecovery, tree
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import compiled
from jedi import debug


def _evaluate_for_annotation(evaluator, annotation):
    if annotation is not None:
        dereferenced_annotation = _fix_forward_reference(evaluator, annotation)
        definitions = evaluator.eval_element(dereferenced_annotation)
        return list(itertools.chain.from_iterable(
            evaluator.execute(d) for d in definitions))
    else:
        return []


def _fix_forward_reference(evaluator, item):
    """
    Gets something from the parse tree, and replaces any string literal
    in there with the result of evaluating that string at the bottom of the
    module
    """
    if isinstance(item, tree.String):
        compiledobjects = evaluator.eval_element(item)
        assert len(compiledobjects) == 1
        compiledobject = list(compiledobjects)[0]
        try:
            p = Parser(load_grammar(), compiledobject.obj, start='eval_input')
            element = p.get_parsed_node()
        except ParseError:
            debug.warning('Annotation not parsed: %s' % compiledobject.obj)
            return item
        else:
            module = item.get_parent_until()
            p.position_modifier.line = module.end_pos[0]
            element.parent = module
            dereferenced = _fix_forward_reference(evaluator, element)
            return dereferenced
    if isinstance(item, tree.Node):
        newnode = tree.Node(item.type, [])
        for child in item.children:
            newchild = _fix_forward_reference(evaluator, child)
            newchild.parent = newnode
            newnode.children.append(newchild)
        newnode.parent = item.parent
        return newnode
    return item


@memoize_default(None, evaluator_is_first_arg=True)
def follow_param(evaluator, param):
    annotation = param.annotation()
    return _evaluate_for_annotation(evaluator, annotation)


@memoize_default(None, evaluator_is_first_arg=True)
def find_return_types(evaluator, func):
    annotation = func.py__annotations__().get("return", None)
    return _evaluate_for_annotation(evaluator, annotation)


# TODO: Memoize
def _get_typing_replacement_module():
    """
    The idea is to return our jedi replacement for the PEP-0484 typing module
    as discussed at https://github.com/davidhalter/jedi/issues/663
    """

    typing_path = os.path.abspath(os.path.join(__file__, "../jedi_typing.py"))
    with open(typing_path) as f:
        code = f.read()
    p = ParserWithRecovery(load_grammar(), code)
    return p.module


def get_types_for_typing_module(evaluator, typ, node):
    from jedi.evaluate.iterable import FakeSequence
    if not typ.base.get_parent_until().name.value == "typing":
        return None
    # we assume that any class using [] in a module called
    # "typing" with a name for which we have a replacement
    # should be replaced by that class. This is not 100%
    # airtight but I don't have a better idea to check that it's
    # actually the PEP-0484 typing module and not some other
    if tree.is_node(node, "subscriptlist"):
        nodes = node.children[::2]  # skip the commas
    else:
        nodes = [node]

    typing = _get_typing_replacement_module()
    factories = evaluator.find_types(typing, "factory")
    assert len(factories) == 1
    factory = list(factories)[0]
    assert factory
    function_body_nodes = factory.children[4].children
    valid_classnames = set(child.name.value
                           for child in function_body_nodes
                           if isinstance(child, tree.Class))
    if typ.name.value not in valid_classnames:
        return None
    compiled_classname = compiled.create(evaluator, typ.name.value)

    result = set()
    # don't know what the last parameter is for, this seems to work :)
    args = FakeSequence(evaluator, nodes, "x-type")

    result |= evaluator.execute_evaluated(factory, compiled_classname, args)
    human_nodes = []
    for node in nodes:
        evalled_node = evaluator.eval_element(node)
        if len(evalled_node) != 1:
            human_nodes.append("???")
            continue
        evalled_node = list(evalled_node)[0]
        try:
            human_nodes.append(str(evalled_node.name))
        except AttributeError:
            pass
        else:
            continue
        try:
            human_nodes.append(evalled_node.obj.__name__)
        except AttributeError:
            pass
        else:
            continue
        human_nodes.append("???")
    for singleresult in result:
        singleresult.name.value += "[%s]" % ", ".join(human_nodes)
    return result
