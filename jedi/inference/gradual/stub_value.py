from jedi.inference.base_value import ValueWrapper
from jedi.inference.value.module import ModuleValue
from jedi.inference.filters import ParserTreeFilter, \
    TreeNameDefinition
from jedi.inference.gradual.typing import TypingModuleFilterWrapper


class StubModuleValue(ModuleValue):
    def __init__(self, non_stub_value_set, *args, **kwargs):
        super(StubModuleValue, self).__init__(*args, **kwargs)
        self.non_stub_value_set = non_stub_value_set

    def is_stub(self):
        return True

    def sub_modules_dict(self):
        """
        We have to overwrite this, because it's possible to have stubs that
        don't have code for all the child modules. At the time of writing this
        there are for example no stubs for `json.tool`.
        """
        names = {}
        for value in self.non_stub_value_set:
            try:
                method = value.sub_modules_dict
            except AttributeError:
                pass
            else:
                names.update(method())
        names.update(super(StubModuleValue, self).sub_modules_dict())
        return names

    def _get_first_non_stub_filters(self):
        for value in self.non_stub_value_set:
            yield next(value.get_filters(search_global=False))

    def _get_stub_filters(self, search_global, **filter_kwargs):
        return [StubFilter(
            value=self,
            search_global=search_global,
            **filter_kwargs
        )] + list(self.iter_star_filters(search_global=search_global))

    def get_filters(self, search_global=False, until_position=None,
                    origin_scope=None, **kwargs):
        filters = super(StubModuleValue, self).get_filters(
            search_global, until_position, origin_scope, **kwargs
        )
        next(filters)  # Ignore the first filter and replace it with our own
        stub_filters = self._get_stub_filters(
            search_global=search_global,
            until_position=until_position,
            origin_scope=origin_scope,
        )
        for f in stub_filters:
            yield f

        for f in filters:
            yield f


class TypingModuleWrapper(StubModuleValue):
    def get_filters(self, *args, **kwargs):
        filters = super(TypingModuleWrapper, self).get_filters(*args, **kwargs)
        yield TypingModuleFilterWrapper(next(filters))
        for f in filters:
            yield f


# From here on down we make looking up the sys.version_info fast.
class _StubName(TreeNameDefinition):
    def infer(self):
        inferred = super(_StubName, self).infer()
        if self.string_name == 'version_info' and self.get_root_value().py__name__() == 'sys':
            return [VersionInfo(c) for c in inferred]
        return inferred


class StubFilter(ParserTreeFilter):
    name_class = _StubName

    def __init__(self, *args, **kwargs):
        self._search_global = kwargs.pop('search_global')  # Python 2 :/
        super(StubFilter, self).__init__(*args, **kwargs)

    def _is_name_reachable(self, name):
        if not super(StubFilter, self)._is_name_reachable(name):
            return False

        if not self._search_global:
            # Imports in stub files are only public if they have an "as"
            # export.
            definition = name.get_definition()
            if definition.type in ('import_from', 'import_name'):
                if name.parent.type not in ('import_as_name', 'dotted_as_name'):
                    return False
            n = name.value
            if n.startswith('_') and not (n.startswith('__') and n.endswith('__')):
                return False
        return True


class VersionInfo(ValueWrapper):
    pass
