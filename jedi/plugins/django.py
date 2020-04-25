"""
Module is used to infer Django model fields.
Bugs:
    - Can't infer ManyToManyField.
"""
from jedi import debug
from jedi.inference.base_value import ValueSet
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


def _infer_field(cls, field_name):
    inference_state = cls.inference_state
    for field_tree_instance in field_name.infer():
        scalar_field = _infer_scalar_field(inference_state, field_name, field_tree_instance)
        if scalar_field is not None:
            return scalar_field

        if field_tree_instance.py__name__() == 'ForeignKey':
            if isinstance(field_tree_instance, TreeInstance):
                # TODO private access..
                argument_iterator = field_tree_instance._arguments.unpack()
                key, lazy_values = next(argument_iterator, (None, None))
                if key is None and lazy_values is not None:
                    for value in lazy_values.infer():
                        if value.py__name__() == 'str':
                            foreign_key_class_name = value.get_safe_value()
                            module = cls.get_root_context()
                            return ValueSet.from_sets(
                                v.execute_with_values()
                                for v in module.py__getattribute__(foreign_key_class_name)
                                if v.is_class()
                            )
                        elif value.is_class():
                            return value.execute_with_values()

    debug.dbg('django plugin: fail to infer `%s` from class `%s`',
              field_name.string_name, cls.py__name__())
    return field_name.infer()


class DjangoModelName(NameWrapper):
    def __init__(self, cls, name):
        super(DjangoModelName, self).__init__(name)
        self._cls = cls

    def infer(self):
        return _infer_field(self._cls, self._wrapped_name)


def _create_manager_for(cls):
    managers = cls.inference_state.import_module(
        ('django', 'db', 'models', 'manager')
    ).py__getattribute__('BaseManager')
    for m in managers:
        if m.is_class() and not m.is_compiled():
            generics_manager = TupleGenericManager((ValueSet([cls]),))
            for c in GenericClass(m, generics_manager).execute_annotation():
                return c
    return None


def _new_dict_filter(cls):
    filter_ = ParserTreeFilter(parent_context=cls.as_context())
    dct = {
        name.string_name: DjangoModelName(cls, name)
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
