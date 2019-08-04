import os

from jedi._compatibility import FileNotFoundError
from jedi.evaluate.names import AbstractArbitraryName
from jedi.api import classes
from jedi.evaluate.helpers import get_str_or_none


def file_name_completions(evaluator, module_context, start_leaf, string, like_name):
    base_name = os.path.basename(string)
    like_name = base_name + like_name
    string = os.path.dirname(string)

    string = _get_string_additions(module_context, start_leaf) + string
    base_path = os.path.join(evaluator.project._path, string)
    try:
        listed = os.listdir(base_path)
    except FileNotFoundError:
        return
    for name in listed:
        if name.startswith(like_name):
            path_for_name = os.path.join(base_path, name)
            if os.path.isdir(path_for_name):
                name += os.path.sep

            yield classes.Completion(
                evaluator,
                FileName(evaluator, name),
                stack=None,
                like_name_length=len(like_name),
            )


def _get_string_additions(module_context, start_leaf):
    addition = start_leaf.get_previous_leaf()
    if addition != '+':
        return ''
    node = addition.parent
    string = ''
    was_addition = True
    for child_node in reversed(node.children[:node.children.index(addition)]):
        if was_addition:
            was_addition = False
            context = module_context.create_context(node)
            contexts = context.eval_node(child_node)
            if len(contexts) != 1:
                return string
            c, = contexts
            s = get_str_or_none(c)
            if s is None:
                return string
            string = s + string
            continue

        if child_node != '+':
            break
        was_addition = True
        child_node
    module_context
    return string


class FileName(AbstractArbitraryName):
    api_type = u'path'
    is_context_name = False
