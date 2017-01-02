# -*- coding: utf-8 -*-
"""
Handles parsing of information out of google style docstrings

CommaneLine:
    # Run the doctests
    tox -e py jedi/evaluate/docscrape_google.py
"""
from __future__ import print_function, division, absolute_import
import re
import sys


def parse_google_args(docstr):
    r"""
    Generates dictionaries of argument hints based on a google docstring

    Args:
        docstr (str): a google-style docstring

    Yields:
        dict: dictionaries of parameter hints

    Example:
        >>> from jedi.evaluate.docscrape_google import *  # NOQA
        >>> docstr = parse_google_args.__doc__
        >>> argdict_list = list(parse_google_args(docstr))
        >>> print([sorted(d.items()) for d in argdict_list])
        [[('name', 'docstr'), ('type', 'str')]]
    """
    blocks = split_google_docblocks(docstr)
    for key, lines in blocks:
        if key == 'Args':
            for argdict in parse_google_argblock(lines):
                yield argdict


def parse_google_returns(docstr):
    r"""
    Generates dictionaries of possible return hints based on a google docstring

    Args:
        docstr (str): a google-style docstring

    Yields:
        dict: dictionaries of return value hints

    Example:
        >>> from jedi.evaluate.docscrape_google import *  # NOQA
        >>> docstr = parse_google_returns.__doc__
        >>> retdict_list = list(parse_google_returns(docstr))
        >>> print([sorted(d.items()) for d in retdict_list])
        [[('type', 'dict')]]
    """
    blocks = split_google_docblocks(docstr)
    for key, lines in blocks:
        if key == 'Returns':
            for retdict in parse_google_retblock(lines):
                yield retdict
        if key == 'Yields':
            for retdict in parse_google_retblock(lines):
                yield retdict


def parse_google_retblock(lines):
    r"""
    Args:
        lines (str): unindented lines from a Returns or Yields section

    Example:
        >>> from jedi.evaluate.docscrape_google import *  # NOQA
        >>> # Test various ways that arglines can be written
        >>> line_list = [
        ...     '',
        ...     'no type, just a description',
        ...     'list: a description',
        ...     'bool: a description\n    with a newline',
        ...     'int or bool: a description',
        ...     'threading.Thread: a description',
        ...     '(int, str): a tuple of int and str',
        ...     'tuple: a tuple of int and str',
        ...     'Tuple[int, str]: a tuple of int and str',
        ...     # Variations without the colon or a description
        ...     'list',
        ...     'Tuple[int, str]',
        ... ]
        >>> lines = '\n'.join(line_list)
        >>> retdict_list = list(parse_google_retblock(lines))
        >>> #print('retdict_list = %s' % (retdict_list),)
        >>> # : only the first of these lines should not parse
        >>> # assert len(retdict_list) == len(line_list) - 2
        >>> # but for now any non-empty line parses
        >>> assert len(retdict_list) == len(line_list) - 1
        >>> # make sure only valid type strings were parsed.
        >>> assert not any(d['type'].startswith(' ') for d in retdict_list)
    """
    # FIXME: Currently this works using a very simple heuristic using a colon
    # to differentiate between the type hint and the description. This can
    # cause an issue if the returns block only contains a description and no
    # type hint. This will work for the majority of cases, but in the future
    # this should be implemented using a parser.
    retdict_list = []
    noindent_pat = re.compile('^[^\s]')
    for line in lines.split('\n'):
        if noindent_pat.match(line):
            parts = line.split(':')
            type_part = parts[0]
            # desc_part = ':'.join(parts[1:])
            # retdict = {'type': type_part, 'desc': desc_part}
            retdict = {'type': type_part}
            retdict_list.append(retdict)
    return retdict_list


def parse_google_argblock(lines):
    r"""
    Args:
        lines (str): the unindented lines from an Args docstring section

    References:
        # It is not clear which of these is *the* standard or if there is one
        https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html#example-google
        http://www.sphinx-doc.org/en/stable/ext/example_google.html#example-google

    Example:
        >>> from jedi.evaluate.docscrape_google import *  # NOQA
        >>> # Test various ways that arglines can be written
        >>> line_list = [
        ...     '',
        ...     'foo1 (int): a description',
        ...     'foo2: a description\n    with a newline',
        ...     'foo3 (int or str): a description',
        ...     'foo4 (int or threading.Thread): a description',
        ...     #
        ...     # this is sphynx-like typing style
        ...     'param1 (:obj:`str`, optional): ',
        ...     'param2 (:obj:`list` of :obj:`str`):',
        ...     #
        ...     # the Type[type] syntax is defined by the python typeing module
        ...     'attr1 (Optional[int]): Description of `attr1`.',
        ...     'attr2 (List[str]): Description of `attr2`.',
        ...     'attr3 (Dict[str, str]): Description of `attr3`.',
        ... ]
        >>> lines = '\n'.join(line_list)
        >>> argdict_list = list(parse_google_argblock(lines))
        >>> # print('argdict_list = %s' % (argdict_list),)
        >>> # All lines except the first should be accepted
        >>> assert len(argdict_list) == len(line_list) - 1
    """
    name_pat = r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)'
    type_pat = r'(?P<type>[^)]*)'
    # Typing is optional
    or_parts = [
        '\(' + type_pat + '\)\s*:',
        '\s*:'
    ]
    type_part = '(' + '|'.join(or_parts) + ')'
    # Each arg hint must defined a on newline without any indentation
    argline_pat = '^' + name_pat + r'\s*' + type_part

    argdict_list = []
    for match in re.finditer(argline_pat, lines, flags=re.M):
        argdict = match.groupdict()
        type_ = argdict['type']
        if type_ is not None:
            pass
        argdict_list.append(argdict)
    return argdict_list


def split_google_docblocks(docstr):
    r"""
    Args:
        docstr (str): a docstring

    Returns:
        list: list of 2-tuples where the first item is a google style docstring
            tag and the second item is the bock corresponding to that tag.

    Example:
        >>> from jedi.evaluate.docscrape_google import *  # NOQA
        >>> docstr = split_google_docblocks.__doc__
        >>> groups = split_google_docblocks(docstr)
        >>> #print('groups = %s' % (groups,))
        >>> assert len(groups) == 3
        >>> print([k for k, v in groups])
        ['Args', 'Returns', 'Example']
    """
    import re
    import textwrap
    import collections

    def get_indentation(line_):
        """ returns number of preceding spaces """
        return len(line_) - len(line_.lstrip())

    # Parse out initial documentation lines
    # Then parse out the blocked lines.
    docstr = textwrap.dedent(docstr)
    docstr_lines = docstr.split('\n')
    line_indent = [get_indentation(line) for line in docstr_lines]
    line_len = [len(line) for line in docstr_lines]

    # The first line may not have the correct indentation if it starts
    # right after the triple quotes. Adjust it in this case to ensure that
    # base indent is always 0
    adjusted = False
    is_nonzero = [len_ > 0 for len_ in line_len]
    if len(line_indent) >= 2:
        if line_len[0] != 0:
            indents = [x for x, f in zip(line_indent, is_nonzero) if f]
            if len(indents) >= 2:
                indent_adjust = min(indents[1:])
                line_indent[0] += indent_adjust
                line_len[0] += indent_adjust
                docstr_lines[0] = (' ' * indent_adjust) + docstr_lines[0]
                adjusted = True
    if adjusted:
        # Redo prepreocessing, but this time on a rectified input
        docstr = textwrap.dedent('\n'.join(docstr_lines))
        docstr_lines = docstr.split('\n')
        line_indent = [get_indentation(line) for line in docstr_lines]
        line_len = [len(line) for line in docstr_lines]

    indents = [x for x, f in zip(line_indent, is_nonzero) if f]
    if len(indents) >= 1:
        if indents[0] != 0:
            print('ERROR IN PARSING')
            print('adjusted = %r' % (adjusted,))
            print(docstr)
            raise AssertionError('Google Style Docstring Missformat')

    base_indent = 0
    # We will group lines by their indentation.
    # Rectify empty lines by giving them their parent's indentation.
    true_indent = []
    prev_indent = None
    for indent_, len_ in zip(line_indent, line_len):
        if len_ == 0:
            # Empty lines take on their parents indentation
            indent_ = prev_indent
        true_indent.append(indent_)
        prev_indent = indent_

    # List of google style tags grouped by alias
    tag_groups = [
        ['Args', 'Arguments', 'Parameters', 'Other Parameters'],
        ['Kwargs', 'Keyword Args', 'Keyword Arguments'],
        ['Warns', 'Warning', 'Warnings'],
        ['Returns', 'Return'],
        ['Example', 'Examples'],
        ['Note', 'Notes'],
        ['Yields', 'Yield'],
        ['Attributes'],
        ['Methods'],
        ['Raises'],
        ['References'],
        ['See Also'],
        ['Todo'],
    ]
    # Map aliased tags to a cannonical name (the first item in the group).
    tag_aliases = dict([(item, group[0]) for group in tag_groups for item in group])
    tag_pattern = '^' + '(' + '|'.join(tag_aliases.keys()) + '): *$'

    group_id = 0
    prev_indent = 0
    group_list = []
    in_tag = False
    for line_num, (line, indent_) in enumerate(zip(docstr_lines, true_indent)):
        if re.match(tag_pattern, line):
            # Check if we can look ahead
            if line_num + 1 < len(docstr_lines):
                # A tag is only valid if its next line is properly indented,
                # empty, or is a tag itself.
                indent_increase = true_indent[line_num + 1] > base_indent
                indent_zero = line_len[line_num + 1] == 0
                matches_tag = re.match(tag_pattern, docstr_lines[line_num + 1])
                if (indent_increase or indent_zero or matches_tag):
                    group_id += 1
                    in_tag = True
            else:
                group_id += 1
                in_tag = True
        # If the indentation goes back to the base, then we have left the tag
        elif in_tag and indent_ != prev_indent and indent_ == base_indent:
            group_id += 1
            in_tag = False
        group_list.append(group_id)
        prev_indent = indent_

    # Group docstr lines by group list
    groups_ = collections.defaultdict(list)
    for groupid, line in zip(group_list, docstr_lines):
        groups_[groupid].append(line)

    groups = []
    line_offset = 0
    for k, lines in groups_.items():
        if len(lines) == 0 or (len(lines) == 1 and len(lines[0]) == 0):
            continue
        elif len(lines) >= 1 and re.match(tag_pattern, lines[0]):
            # An encoded google sub-block
            key = lines[0].strip().rstrip(':')
            val = lines[1:]
            subblock = textwrap.dedent('\n'.join(val))
        else:
            # A top level text documentation block
            key = '__DOC__'
            val = lines[:]
            subblock = '\n'.join(val)

        key = tag_aliases.get(key, key)
        groups.append((key, subblock))
        line_offset += len(lines)
    return groups
