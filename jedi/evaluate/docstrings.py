"""
Docstrings are another source of information for functions and classes.
:mod:`jedi.evaluate.dynamic` tries to find all executions of functions, while
the docstring parsing is much easier. There are two different types of
docstrings that |jedi| understands:

- `Sphinx <http://sphinx-doc.org/markup/desc.html#info-field-lists>`_
- `Epydoc <http://epydoc.sourceforge.net/manual-fields.html>`_

For example, the sphinx annotation ``:type foo: str`` clearly states that the
type of ``foo`` is ``str``.

As an addition to parameter searching, this module also provides return
annotations.
"""

import re
from textwrap import dedent

from jedi.evaluate.cache import memoize_default
from jedi.parser import Parser
from jedi.common import indent_block

DOCSTRING_PARAM_PATTERNS = [
    r'\s*:type\s+%s:\s*([^\n]+)',  # Sphinx
    r'\s*@type\s+%s:\s*([^\n]+)',  # Epydoc
]

DOCSTRING_RETURN_PATTERNS = [
    re.compile(r'\s*:rtype:\s*([^\n]+)', re.M),  # Sphinx
    re.compile(r'\s*@rtype:\s*([^\n]+)', re.M),  # Epydoc
]

REST_ROLE_PATTERN = re.compile(r':[^`]+:`([^`]+)`')


@memoize_default(None, evaluator_is_first_arg=True)
def follow_param(evaluator, param):
    func = param.parent_function
    param_str = _search_param_in_docstr(func.raw_doc, str(param.get_name()))

    code = dedent("""
    def pseudo_docstring_stuff():
        '''Create a pseudo function for docstring statements.'''
    %s
    """)
    if param_str is not None:
        for element in re.findall('((?:\w+\.)*\w+)\.', param_str):
            # Try to import module part in dotted name.
            # (e.g., 'threading' in 'threading.Thread').
            param_str = 'import %s\n' % element + param_str

        p = Parser(code % indent_block(param_str), no_docstr=True)
        pseudo_cls = p.module.subscopes[0]
        try:
            stmt = pseudo_cls.statements[-1]
        except IndexError:
            return []

        # Use the module of the param.
        # TODO this module is not the module of the param in case of a function
        # call. In that case it's the module of the function call.
        # stuffed with content from a function call.
        pseudo_cls.parent = param.get_parent_until()
        return evaluator.eval_statement(stmt)
    return []


def _search_param_in_docstr(docstr, param_str):
    """
    Search `docstr` for a type of `param_str`.

    >>> _search_param_in_docstr(':type param: int', 'param')
    'int'
    >>> _search_param_in_docstr('@type param: int', 'param')
    'int'
    >>> _search_param_in_docstr(
    ...   ':type param: :class:`threading.Thread`', 'param')
    'threading.Thread'
    >>> _search_param_in_docstr('no document', 'param') is None
    True

    """
    # look at #40 to see definitions of those params
    patterns = [re.compile(p % re.escape(param_str))
                for p in DOCSTRING_PARAM_PATTERNS]
    for pattern in patterns:
        match = pattern.search(docstr)
        if match:
            return _strip_rest_role(match.group(1))

    return None


def _strip_rest_role(type_str):
    """
    Strip off the part looks like a ReST role in `type_str`.

    >>> _strip_rest_role(':class:`ClassName`')  # strip off :class:
    'ClassName'
    >>> _strip_rest_role(':py:obj:`module.Object`')  # works with domain
    'module.Object'
    >>> _strip_rest_role('ClassName')  # do nothing when not ReST role
    'ClassName'

    See also:
    http://sphinx-doc.org/domains.html#cross-referencing-python-objects

    """
    match = REST_ROLE_PATTERN.match(type_str)
    if match:
        return match.group(1)
    else:
        return type_str


@memoize_default(None, evaluator_is_first_arg=True)
def find_return_types(evaluator, func):
    def search_return_in_docstr(code):
        for p in DOCSTRING_RETURN_PATTERNS:
            match = p.search(code)
            if match:
                return match.group(1)

    type_str = search_return_in_docstr(func.raw_doc)
    if not type_str:
        return []

    p = Parser(type_str, None, no_docstr=True)
    stmt = p.module.get_statement_for_position((1, 0))
    if stmt is None:
        return []
    stmt.parent = func
    return list(evaluator.eval_statement(stmt))
