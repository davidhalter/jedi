from jedi._compatibility import utf8_repr, encoding, is_py3


class _NodeOrLeaf(object):
    """
    This is just here to have an isinstance check, which is also used on
    evaluate classes. But since they have sometimes a special type of
    delegation, it is important for those classes to override this method.

    I know that there is a chance to do such things with __instancecheck__, but
    since Python 2.5 doesn't support it, I decided to do it this way.
    """
    __slots__ = ()

    def get_root_node(self):
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def get_next_sibling(self):
        """
        The node immediately following the invocant in their parent's children
        list. If the invocant does not have a next sibling, it is None
        """
        # Can't use index(); we need to test by identity
        for i, child in enumerate(self.parent.children):
            if child is self:
                try:
                    return self.parent.children[i + 1]
                except IndexError:
                    return None

    def get_previous_sibling(self):
        """
        The node/leaf immediately preceding the invocant in their parent's
        children list. If the invocant does not have a previous sibling, it is
        None.
        """
        # Can't use index(); we need to test by identity
        for i, child in enumerate(self.parent.children):
            if child is self:
                if i == 0:
                    return None
                return self.parent.children[i - 1]

    def get_previous_leaf(self):
        """
        Returns the previous leaf in the parser tree.
        Raises an IndexError if it's the first element.
        """
        node = self
        while True:
            c = node.parent.children
            i = c.index(node)
            if i == 0:
                node = node.parent
                if node.parent is None:
                    return None
            else:
                node = c[i - 1]
                break

        while True:
            try:
                node = node.children[-1]
            except AttributeError:  # A Leaf doesn't have children.
                return node

    def get_next_leaf(self):
        """
        Returns the previous leaf in the parser tree.
        Raises an IndexError if it's the last element.
        """
        node = self
        while True:
            c = node.parent.children
            i = c.index(node)
            if i == len(c) - 1:
                node = node.parent
                if node.parent is None:
                    return None
            else:
                node = c[i + 1]
                break

        while True:
            try:
                node = node.children[0]
            except AttributeError:  # A Leaf doesn't have children.
                return node


class Leaf(_NodeOrLeaf):
    __slots__ = ('value', 'parent', 'line', 'indent', 'prefix')

    def __init__(self, value, start_pos, prefix=''):
        self.value = value
        self.start_pos = start_pos
        self.prefix = prefix
        self.parent = None

    @property
    def start_pos(self):
        return self.line, self.indent

    @start_pos.setter
    def start_pos(self, value):
        self.line = value[0]
        self.indent = value[1]

    def get_start_pos_of_prefix(self):
        previous_leaf = self.get_previous_leaf()
        if previous_leaf is None:
            return self.line - self.prefix.count('\n'), 0  # It's the first leaf.
        return previous_leaf.end_pos

    def move(self, line_offset):
        self.line += line_offset

    def get_first_leaf(self):
        return self

    def get_last_leaf(self):
        return self

    def get_code(self, normalized=False, include_prefix=True):
        if normalized:
            return self.value
        if include_prefix:
            return self.prefix + self.value
        else:
            return self.value

    def nodes_to_execute(self, last_added=False):
        return []

    @property
    def end_pos(self):
        """
        Literals and whitespace end_pos are more complicated than normal
        end_pos, because the containing newlines may change the indexes.
        """
        lines = self.value.split('\n')
        end_pos_line = self.line + len(lines) - 1
        # Check for multiline token
        if self.line == end_pos_line:
            end_pos_indent = self.indent + len(lines[-1])
        else:
            end_pos_indent = len(lines[-1])
        return end_pos_line, end_pos_indent

    @utf8_repr
    def __repr__(self):
        return "<%s: %s start=%s>" % (type(self).__name__, self.value, self.start_pos)


class BaseNode(_NodeOrLeaf):
    """
    The super class for all nodes.

    If you create custom nodes, you will probably want to inherit from this
    ``BaseNode``.
    """
    __slots__ = ('children', 'parent')
    type = None

    def __init__(self, children):
        """
        Initialize :class:`BaseNode`.

        :param children: The module in which this Python object locates.
        """
        for c in children:
            c.parent = self
        self.children = children
        self.parent = None

    def move(self, line_offset):
        """
        Move the Node's start_pos.
        """
        for c in self.children:
            c.move(line_offset)

    @property
    def start_pos(self):
        return self.children[0].start_pos

    def get_start_pos_of_prefix(self):
        return self.children[0].get_start_pos_of_prefix()

    @property
    def end_pos(self):
        return self.children[-1].end_pos

    def _get_code_for_children(self, children, normalized, include_prefix):
        # TODO implement normalized (depending on context).
        if include_prefix:
            return "".join(c.get_code(normalized) for c in children)
        else:
            first = children[0].get_code(include_prefix=False)
            return first + "".join(c.get_code(normalized) for c in children[1:])

    def get_code(self, normalized=False, include_prefix=True):
        return self._get_code_for_children(self.children, normalized, include_prefix)

    def get_leaf_for_position(self, position, include_prefixes=False):
        def binary_search(lower, upper):
            if lower == upper:
                element = self.children[lower]
                if not include_prefixes and position < element.start_pos:
                    # We're on a prefix.
                    return None
                # In case we have prefixes, a leaf always matches
                try:
                    return element.get_leaf_for_position(position, include_prefixes)
                except AttributeError:
                    return element


            index = int((lower + upper) / 2)
            element = self.children[index]
            if position <= element.end_pos:
                return binary_search(lower, index)
            else:
                return binary_search(index + 1, upper)

        if not ((1, 0) <= position <= self.children[-1].end_pos):
            raise ValueError('Please provide a position that exists within this node.')
        return binary_search(0, len(self.children) - 1)

    def get_first_leaf(self):
        return self.children[0].get_first_leaf()

    def get_last_leaf(self):
        return self.children[-1].get_last_leaf()

    def get_following_comment_same_line(self):
        """
        returns (as string) any comment that appears on the same line,
        after the node, including the #
        """
        try:
            if self.type == 'for_stmt':
                whitespace = self.children[5].get_first_leaf().prefix
            elif self.type == 'with_stmt':
                whitespace = self.children[3].get_first_leaf().prefix
            else:
                whitespace = self.get_last_leaf().get_next_leaf().prefix
        except AttributeError:
            return None
        except ValueError:
            # TODO in some particular cases, the tree doesn't seem to be linked
            # correctly
            return None
        if "#" not in whitespace:
            return None
        comment = whitespace[whitespace.index("#"):]
        if "\r" in comment:
            comment = comment[:comment.index("\r")]
        if "\n" in comment:
            comment = comment[:comment.index("\n")]
        return comment

    @utf8_repr
    def __repr__(self):
        code = self.get_code().replace('\n', ' ').strip()
        if not is_py3:
            code = code.encode(encoding, 'replace')
        return "<%s: %s@%s,%s>" % \
            (type(self).__name__, code, self.start_pos[0], self.start_pos[1])


class Node(BaseNode):
    """Concrete implementation for interior nodes."""
    __slots__ = ('type',)

    _IGNORE_EXECUTE_NODES = set([
        'suite', 'subscriptlist', 'subscript', 'simple_stmt', 'sliceop',
        'testlist_comp', 'dictorsetmaker', 'trailer', 'decorators',
        'decorated', 'arglist', 'argument', 'exprlist', 'testlist',
        'testlist_safe', 'testlist1'
    ])

    def __init__(self, type, children):
        """
        Initializer.

        Takes a type constant (a symbol number >= 256), a sequence of
        child nodes, and an optional context keyword argument.

        As a side effect, the parent pointers of the children are updated.
        """
        super(Node, self).__init__(children)
        self.type = type

    def nodes_to_execute(self, last_added=False):
        """
        For static analysis.
        """
        result = []
        if self.type not in Node._IGNORE_EXECUTE_NODES and not last_added:
            result.append(self)
            last_added = True

        for child in self.children:
            result += child.nodes_to_execute(last_added)
        return result

    def __repr__(self):
        return "%s(%s, %r)" % (self.__class__.__name__, self.type, self.children)


class ErrorNode(BaseNode):
    """
    TODO doc
    """
    __slots__ = ()
    type = 'error_node'

    def nodes_to_execute(self, last_added=False):
        return []


class ErrorLeaf(Leaf):
    """
    TODO doc
    """
    __slots__ = ('original_type')
    type = 'error_leaf'

    def __init__(self, original_type, value, start_pos, prefix=''):
        super(ErrorLeaf, self).__init__(value, start_pos, prefix)
        self.original_type = original_type

    def __repr__(self):
        return "<%s: %s:%s, %s)>" % \
            (type(self).__name__, self.original_type, repr(self.value), self.start_pos)


