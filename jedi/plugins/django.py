"""
Module is used to infer Django model fields.
"""
from jedi import debug
from jedi.inference.base_value import ValueSet, iterator_to_value_set
from jedi.inference.filters import ParserTreeFilter, DictFilter
from jedi.inference.names import NameWrapper
from jedi.inference.value.instance import TreeInstance
from jedi.inference.gradual.base import GenericClass
from jedi.inference.gradual.generics import TupleGenericManager


mapping = {
    'IntegerField': (None, 'int'),
    'BigIntegerField': (None, 'int'),
    'PositiveIntegerField': (None, 'int'),
    'SmallIntegerField': (None, 'int'),
    'CharField': (None, 'str'),
    'TextField': (None, 'str'),
    'EmailField': (None, 'str'),
    'FloatField': (None, 'float'),
    'BinaryField': (None, 'bytes'),
    'BooleanField': (None, 'bool'),
    'DecimalField': ('decimal', 'Decimal'),
    'TimeField': ('datetime', 'time'),
    'DurationField': ('datetime', 'timedelta'),
    'DateField': ('datetime', 'date'),
    'DateTimeField': ('datetime', 'datetime'),
}


def _infer_scalar_field(inference_state, field_name, field_tree_instance):
    try:
        module_name, attribute_name = mapping[field_tree_instance.py__name__()]
    except KeyError:
        return None

    if module_name is None:
        module = inference_state.builtins_module
    else:
        module = inference_state.import_module((module_name,))

    for attribute in module.py__getattribute__(attribute_name):
        return attribute.execute_with_values()


@iterator_to_value_set
def _get_foreign_key_values(cls, field_tree_instance):
    if isinstance(field_tree_instance, TreeInstance):
        # TODO private access..
        argument_iterator = field_tree_instance._arguments.unpack()
        key, lazy_values = next(argument_iterator, (None, None))
        if key is None and lazy_values is not None:
            for value in lazy_values.infer():
                if value.py__name__() == 'str':
                    foreign_key_class_name = value.get_safe_value()
                    module = cls.get_root_context()
                    for v in module.py__getattribute__(foreign_key_class_name):
                        if v.is_class():
                            yield v
                elif value.is_class():
                    yield value


def _infer_field(cls, field_name):
    inference_state = cls.inference_state
    for field_tree_instance in field_name.infer():
        scalar_field = _infer_scalar_field(inference_state, field_name, field_tree_instance)
        if scalar_field is not None:
            return scalar_field

        name = field_tree_instance.py__name__()
        is_many_to_many = name == 'ManyToManyField'
        if name == 'ForeignKey' or is_many_to_many:
            values = _get_foreign_key_values(cls, field_tree_instance)
            if is_many_to_many:
                return ValueSet(filter(None, [
                    _create_manager_for(v, 'RelatedManager') for v in values
                ]))
            else:
                return values.execute_with_values()

    debug.dbg('django plugin: fail to infer `%s` from class `%s`',
              field_name.string_name, cls.py__name__())
    return field_name.infer()


class DjangoModelName(NameWrapper):
    def __init__(self, cls, name):
        super(DjangoModelName, self).__init__(name)
        self._cls = cls

    def infer(self):
        return _infer_field(self._cls, self._wrapped_name)


def _create_manager_for(cls, manager_cls='BaseManager'):
    managers = cls.inference_state.import_module(
        ('django', 'db', 'models', 'manager')
    ).py__getattribute__(manager_cls)
    for m in managers:
        if m.is_class() and not m.is_compiled():
            generics_manager = TupleGenericManager((ValueSet([cls]),))
            for c in GenericClass(m, generics_manager).execute_annotation():
                return c
    return None


def _new_dict_filter(cls):
    filters = cls.get_filters(is_instance=True, include_metaclasses=False)
    dct = {
        name.string_name: DjangoModelName(cls, name)
        for filter_ in reversed(list(filters))
        for name in filter_.values()
    }
    manager = _create_manager_for(cls)
    if manager:
        dct['objects'] = manager.name
    return DictFilter(dct)


def get_metaclass_filters(func):
    def wrapper(cls, metaclasses):
        for metaclass in metaclasses:
            if metaclass.py__name__() == 'ModelBase' \
                    and metaclass.get_root_context().py__name__() == 'django.db.models.base':
                return [_new_dict_filter(cls)]

        return func(cls, metaclasses)
    return wrapper
