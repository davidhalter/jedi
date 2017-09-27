"""
Functions evaluating the syntax tree.
"""

from jedi import debug


def eval_trailer(context, base_contexts, trailer):
    trailer_op, node = trailer.children[:2]
    if node == ')':  # `arglist` is optional.
        node = ()

    if trailer_op == '[':
        from jedi.evaluate import iterable
        return iterable.py__getitem__(context.evaluator, context, base_contexts, trailer)
    else:
        debug.dbg('eval_trailer: %s in %s', trailer, base_contexts)
        if trailer_op == '.':
            return base_contexts.py__getattribute__(
                name_context=context,
                name_or_str=node
            )
        else:
            assert trailer_op == '('
            from jedi.evaluate import param
            arguments = param.TreeArguments(context.evaluator, context, node, trailer)
            return base_contexts.execute(arguments)
