from abc import abstractmethod

from jedi.inference.filters import ParserTreeFilter, MergedFilter, \
    GlobalNameFilter
from jedi import parser_utils


class AbstractContext(object):
    """
    Should be defined, otherwise the API returns empty types.
    """
    predefined_names = {}

    def __init__(self, value):
        self.inference_state = value.inference_state
        self._value = value

    @abstractmethod
    def get_filters(self, until_position=None, origin_scope=None):
        raise NotImplementedError

    def get_root_context(self):
        return self._value.get_root_context()

    def create_value(self, node):
        from jedi.inference import value

        if node == self.tree_node:
            assert self.is_module()
            return self.get_value()

        parent_context = self.create_context(node)

        if node.type in ('funcdef', 'lambdef'):
            func = value.FunctionValue.from_context(parent_context, node)
            if parent_context.is_class():
                # TODO _value private access!
                instance = value.AnonymousInstance(
                    self.inference_state, parent_context.parent_context, parent_context._value)
                func = value.BoundMethod(
                    instance=instance,
                    function=func
                )
            return func
        elif node.type == 'classdef':
            return value.ClassValue(self.inference_state, parent_context, node)
        else:
            raise NotImplementedError("Probably shouldn't happen: %s" % node)

    def create_context(self, node):
        def from_scope_node(scope_node, is_nested=True):
            if scope_node == self.tree_node:
                return self

            if scope_node.type in ('funcdef', 'lambdef', 'classdef'):
                return self.create_value(scope_node).as_context()
            elif scope_node.type in ('comp_for', 'sync_comp_for'):
                parent_scope = parser_utils.get_parent_scope(scope_node)
                parent_context = from_scope_node(parent_scope)
                if node.start_pos >= scope_node.children[-1].start_pos:
                    return parent_context
                return CompForContext(parent_context, scope_node)
            raise Exception("There's a scope that was not managed: %s" % scope_node)

        def parent_scope(node):
            while True:
                node = node.parent

                if parser_utils.is_scope(node):
                    return node
                elif node.type in ('argument', 'testlist_comp'):
                    if node.children[1].type in ('comp_for', 'sync_comp_for'):
                        return node.children[1]
                elif node.type == 'dictorsetmaker':
                    for n in node.children[1:4]:
                        # In dictionaries it can be pretty much anything.
                        if n.type in ('comp_for', 'sync_comp_for'):
                            return n

        scope_node = parent_scope(node)
        if scope_node.type in ('funcdef', 'classdef'):
            colon = scope_node.children[scope_node.children.index(':')]
            if node.start_pos < colon.start_pos:
                parent = node.parent
                if not (parent.type == 'param' and parent.name == node):
                    scope_node = parent_scope(scope_node)
        return from_scope_node(scope_node, is_nested=True)

    def goto(self, name_or_str, position):
        from jedi.inference import finder
        f = finder.NameFinder(self.inference_state, self, self, name_or_str, position)
        filters = f.get_global_filters()
        return f.filter_name(filters)

    def py__getattribute__(self, name_or_str, name_value=None, position=None,
                           analysis_errors=True):
        """
        :param position: Position of the last statement -> tuple of line, column
        """
        if name_value is None:
            name_value = self
        from jedi.inference import finder
        f = finder.NameFinder(self.inference_state, self, name_value, name_or_str,
                              position, analysis_errors=analysis_errors)
        filters = f.get_global_filters()
        return f.find(filters, attribute_lookup=False)

    @property
    def tree_node(self):
        return self._value.tree_node

    @property
    def parent_context(self):
        return self._value.parent_context

    def is_module(self):
        return self._value.is_module()

    def is_builtins_module(self):
        return self._value == self.inference_state.builtins_module

    def is_class(self):
        return self._value.is_class()

    def is_stub(self):
        return self._value.is_stub()

    def is_instance(self):
        return self._value.is_instance()

    def is_compiled(self):
        return self._value.is_compiled()

    def py__name__(self):
        return self._value.py__name__()

    def get_qualified_names(self):
        return self._value.get_qualified_names()

    def py__doc__(self):
        return self._value.py__doc__()

    def infer_node(self, node):
        return self.inference_state.infer_element(self, node)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._value)


class FunctionContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        yield ParserTreeFilter(
            self.inference_state,
            parent_context=self,
            until_position=until_position,
            origin_scope=origin_scope
        )


class ModuleContext(AbstractContext):
    def py__file__(self):
        return self._value.py__file__()

    @property
    def py__package__(self):
        return self._value.py__package__

    @property
    def is_package(self):
        return self._value.is_package

    def get_filters(self, until_position=None, origin_scope=None):
        filters = self._value.get_filters(origin_scope)
        # Skip the first filter and replace it.
        next(filters)
        yield MergedFilter(
            ParserTreeFilter(
                parent_context=self,
                until_position=until_position,
                origin_scope=origin_scope
            ),
            GlobalNameFilter(self, self.tree_node),
        )
        for f in filters:  # Python 2...
            yield f

    @property
    def string_names(self):
        return self._value.string_names

    @property
    def code_lines(self):
        return self._value.code_lines

    def get_value(self):
        """
        This is the only function that converts a context back to a value.
        This is necessary for stub -> python conversion and vice versa. However
        this method shouldn't be move to AbstractContext.
        """
        return self._value


class NamespaceContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        return self._value.get_filters()

    def py__file__(self):
        return self._value.py__file__()


class ClassContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        yield self.get_global_filter(until_position, origin_scope)

    def get_global_filter(self, until_position=None, origin_scope=None):
        return ParserTreeFilter(
            parent_context=self,
            until_position=until_position,
            origin_scope=origin_scope
        )


class CompForContext(AbstractContext):
    def __init__(self, parent_context, comp_for):
        self._parent_context = parent_context
        self.inference_state = parent_context.inference_state
        self._tree_node = comp_for

    @property
    def parent_context(self):
        return self._parent_context

    def get_root_context(self):
        return self._parent_context.get_root_context()

    def is_instance(self):
        return False

    def is_compiled(self):
        return False

    @property
    def tree_node(self):
        return self._tree_node

    def get_filters(self, until_position=None, origin_scope=None):
        yield ParserTreeFilter(self)


class CompiledContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        return self._value.get_filters()

    def get_value(self):
        return self._value

    def py__file__(self):
        return self._value.py__file__()
