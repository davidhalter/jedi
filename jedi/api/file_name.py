import os

from jedi._compatibility import FileNotFoundError, force_unicode
from jedi.evaluate.names import AbstractArbitraryName
from jedi.api import classes
from jedi.evaluate.helpers import get_str_or_none


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
            if os.path.isdir(path_for_name) and not is_in_os_path_join:
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
    return _add_strings(module_context, reversed(list(iterate_nodes())))


def _add_strings(module_context, nodes, add_slash=False):
    string = ''
    context = None
    first = True
    for child_node in nodes:
        if context is None:
            context = module_context.create_context(child_node)
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
    arglist = start_leaf.parent
    if arglist.type == 'arglist':
        trailer = arglist.parent
        if trailer.type == 'trailer':
            atom = trailer.get_previous_sibling()
            if atom.type != 'trailer':
                context = module_context.create_context(atom)
                contexts = context.eval_node(atom)
                if any([c.name.get_qualified_names(include_module_names=True)
                        != ('os', 'path', 'join') for c in contexts]):
                    return string, False
                nodes = arglist.children[:arglist.children.index(start_leaf):2]
                return _add_strings(module_context, nodes, add_slash=True), True

    return string, False
