import os

from jedi._compatibility import FileNotFoundError, force_unicode
from jedi.evaluate.names import AbstractArbitraryName
from jedi.api import classes
from jedi.evaluate.helpers import get_str_or_none
from jedi.parser_utils import get_string_quote


def file_name_completions(evaluator, module_context, start_leaf, string, like_name):
    # First we want to find out what can actually be changed as a name.
    like_name_length = len(os.path.basename(string) + like_name)

    addition = _get_string_additions(module_context, start_leaf)
    if addition is None:
        return
    string = addition + string

    # Here we use basename again, because if strings are added like
    # `'foo' + 'bar`, it should complete to `foobar/`.
    must_start_with = os.path.basename(string) + like_name
    string = os.path.dirname(string)

    string, is_in_os_path_join = _maybe_add_os_path_join(module_context, start_leaf, string)
    base_path = os.path.join(evaluator.project._path, string)
    try:
        listed = os.listdir(base_path)
    except FileNotFoundError:
        return
    for name in listed:
        if name.startswith(must_start_with):
            path_for_name = os.path.join(base_path, name)
            if is_in_os_path_join:
                if start_leaf.type == 'string':
                    name += get_string_quote(start_leaf)
                else:
                    assert start_leaf.type == 'error_leaf'
                    name += start_leaf.value
            elif os.path.isdir(path_for_name):
                name += os.path.sep

            yield classes.Completion(
                evaluator,
                FileName(evaluator, name[len(must_start_with) - like_name_length:]),
                stack=None,
                like_name_length=like_name_length
            )


def _get_string_additions(module_context, start_leaf):
    def iterate_nodes():
        node = addition.parent
        was_addition = True
        for child_node in reversed(node.children[:node.children.index(addition)]):
            if was_addition:
                was_addition = False
                yield child_node
                continue

            if child_node != '+':
                break
            was_addition = True

    addition = start_leaf.get_previous_leaf()
    if addition != '+':
        return ''
    context = module_context.create_context(start_leaf)
    return _add_strings(context, reversed(list(iterate_nodes())))


def _add_strings(context, nodes, add_slash=False):
    string = ''
    first = True
    for child_node in nodes:
        contexts = context.eval_node(child_node)
        if len(contexts) != 1:
            return None
        c, = contexts
        s = get_str_or_none(c)
        if s is None:
            return None
        if not first and add_slash:
            string += os.path.sep
        string += force_unicode(s)
        first = False
    return string


class FileName(AbstractArbitraryName):
    api_type = u'path'
    is_context_name = False


def _maybe_add_os_path_join(module_context, start_leaf, string):
    def check_for_power(join_atom, nodes):
        context = module_context.create_context(join_atom)
        contexts = context.eval_node(join_atom)
        if any([c.name.get_qualified_names(include_module_names=True)
                != ('os', 'path', 'join') for c in contexts]):
            return string, False
        return _add_strings(context, nodes, add_slash=True), True

    def check_trailer(trailer, arglist_nodes):
        atom = trailer.get_previous_sibling()
        if atom.type != 'trailer' and trailer.children[0] == '(':
            return check_for_power(atom, arglist_nodes)
        return string, False

    # Maybe an arglist or some weird error case. Therefore checked below.
    arglist = start_leaf.parent
    index = arglist.children.index(start_leaf)
    arglist_nodes = arglist.children[:index]
    if start_leaf.type == 'error_leaf':
        # Unfinished string literal, like `join('`
        if index > 0:
            error_node = arglist_nodes[-1]
            if error_node.type == 'error_node' and len(error_node.children) >= 2:
                index = -2
                if error_node.children[-1].type == 'arglist':
                    arglist_nodes = error_node.children[-1].children
                    index -= 1
                else:
                    arglist_nodes = []

                if error_node.children[index + 1] == '(':
                    atom = error_node.children[index]
                    if atom.type in ('atom_expr', 'power', 'name'):
                        return check_for_power(atom, arglist_nodes[::2])
    elif arglist.type == 'arglist':
        trailer = arglist.parent
        if trailer.type == 'error_node':
            trailer_index = trailer.children.index(arglist)
            assert trailer_index >= 2
            assert trailer.children[trailer_index - 1] == '('
            name = trailer.children[trailer_index - 2]
            if name.type in ('atom_expr', 'power', 'name'):
                return check_for_power(name, arglist_nodes[::2])
        elif trailer.type == 'trailer':
            return check_trailer(trailer, arglist_nodes[::2])
    elif arglist.type == 'trailer':
        return check_trailer(arglist, [])
    elif arglist.type == 'error_node':
        # Stuff like `join(""`
        if len(arglist_nodes) >= 2 and arglist_nodes[-1] == '(':
            name = arglist_nodes[-2]
            if name.type in ('atom_expr', 'power', 'name'):
                return check_for_power(name, [])

    return string, False
