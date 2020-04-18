"""
Module is used to infer Django model fields.
"""
from jedi.inference.base_value import LazyValueWrapper
from jedi.inference.utils import safe_property
from jedi.inference.filters import ParserTreeFilter, DictFilter
from jedi.inference.names import ValueName
from jedi.inference.value.instance import TreeInstance


def new_dict_filter(cls):
    filter_ = ParserTreeFilter(parent_context=cls.as_context())
    res = {f.string_name: _infer_field(cls, f) for f in filter_.values()}
    return [DictFilter({x: y for x, y in res.items() if y is not None})]


class DjangoModelField(LazyValueWrapper):
    def __init__(self, cls, name):
        self.inference_state = cls.inference_state
        self._cls = cls  # Corresponds to super().__self__
        self._name = name
        self.tree_node = self._name.tree_name

    @safe_property
    def name(self):
        return ValueName(self, self._name.tree_name)

    def _get_wrapped_value(self):
        obj, = self._cls.execute_with_values()
        return obj


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


def _infer_scalar_field(cls, field, field_tree_instance):
    if field_tree_instance.name.string_name not in mapping:
        return None

    module_name, attribute_name = mapping[field_tree_instance.name.string_name]
    if module_name is None:
        module = cls.inference_state.builtins_module
    else:
        module = cls.inference_state.import_module((module_name,))

    attribute, = module.py__getattribute__(attribute_name)
    return DjangoModelField(attribute, field).name


def _infer_field(cls, field):
    field_tree_instance, = field.infer()
    scalar_field = _infer_scalar_field(cls, field, field_tree_instance)
    if scalar_field:
        return scalar_field

    if field_tree_instance.name.string_name == 'ForeignKey':
        if isinstance(field_tree_instance, TreeInstance):
             argument_iterator = field_tree_instance._arguments.unpack()
             key, lazy_values = next(argument_iterator, (None, None))
             if key is None and lazy_values is not None:
                 for value in lazy_values.infer():
                     if value.name.string_name == 'str':
                         foreign_key_class_name = value.get_safe_value()
                         for v in cls.parent_context.py__getattribute__(foreign_key_class_name):
                             return DjangoModelField(v, field).name
                     else:
                         return DjangoModelField(value, field).name

    print('TODO: {}'.format(field))


def get_metaclass_filters(func):
    def wrapper(cls, metaclasses):
        for metaclass in metaclasses:
            if metaclass.py__name__() == 'ModelBase' \
                    and metaclass.get_root_context().py__name__() == 'django.db.models.base':
                django_dict_filter = new_dict_filter(cls)
                if django_dict_filter is not None:
                    return django_dict_filter

        return func(cls, metaclasses)
    return wrapper
