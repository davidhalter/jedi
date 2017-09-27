"""
Functions evaluating the syntax tree.
"""

from parso.python import tree

from jedi import debug
from jedi import parser_utils
from jedi.evaluate.context import ContextSet
from jedi.evaluate import compiled
from jedi.evaluate import precedence


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


def eval_atom(context, atom):
    """
    Basically to process ``atom`` nodes. The parser sometimes doesn't
    generate the node (because it has just one child). In that case an atom
    might be a name or a literal as well.
    """
    from jedi.evaluate import iterable
    if atom.type == 'name':
        # This is the first global lookup.
        stmt = tree.search_ancestor(
            atom, 'expr_stmt', 'lambdef'
        ) or atom
        if stmt.type == 'lambdef':
            stmt = atom
        return context.py__getattribute__(
            name_or_str=atom,
            position=stmt.start_pos,
            search_global=True
        )

    elif isinstance(atom, tree.Literal):
        string = parser_utils.safe_literal_eval(atom.value)
        return ContextSet(compiled.create(context.evaluator, string))
    else:
        c = atom.children
        if c[0].type == 'string':
            # Will be one string.
            context_set = eval_atom(context, c[0])
            for string in c[1:]:
                right = eval_atom(context, string)
                context_set = precedence.calculate(context.evaluator, context, context_set, '+', right)
            return context_set
        # Parentheses without commas are not tuples.
        elif c[0] == '(' and not len(c) == 2 \
                and not(c[1].type == 'testlist_comp' and
                        len(c[1].children) > 1):
            return context.eval_node(c[1])

        try:
            comp_for = c[1].children[1]
        except (IndexError, AttributeError):
            pass
        else:
            if comp_for == ':':
                # Dict comprehensions have a colon at the 3rd index.
                try:
                    comp_for = c[1].children[3]
                except IndexError:
                    pass

            if comp_for.type == 'comp_for':
                return ContextSet(iterable.Comprehension.from_atom(context.evaluator, context, atom))

        # It's a dict/list/tuple literal.
        array_node = c[1]
        try:
            array_node_c = array_node.children
        except AttributeError:
            array_node_c = []
        if c[0] == '{' and (array_node == '}' or ':' in array_node_c):
            context = iterable.DictLiteralContext(context.evaluator, context, atom)
        else:
            context = iterable.SequenceLiteralContext(context.evaluator, context, atom)
        return ContextSet(context)
