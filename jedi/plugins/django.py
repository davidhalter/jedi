"""
Module provides infering of Django model fields.
"""
from jedi.inference.base_value import LazyValueWrapper
from jedi.inference.utils import safe_property
from jedi.inference.filters import ParserTreeFilter, DictFilter
from jedi.inference.names import ValueName
from jedi.inference.value.instance import TreeInstance


def new_dict_filter(cls):
    filter_ = ParserTreeFilter(parent_context=cls.as_context())
    return [DictFilter({
        f.string_name: _infer_field(cls, f) for f in filter_.values()
    })]


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


def _infer_field(cls, field):
    field_tree_instance, = field.infer()

    if field_tree_instance.name.string_name in ('CharField', 'TextField', 'EmailField'):
        model_instance_field_type, = cls.inference_state.builtins_module.py__getattribute__('str')
        return DjangoModelField(model_instance_field_type, field).name

    integer_field_classes = ('IntegerField', 'BigIntegerField', 'PositiveIntegerField', 'SmallIntegerField')
    if field_tree_instance.name.string_name in integer_field_classes:
        model_instance_field_type, = cls.inference_state.builtins_module.py__getattribute__('int')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'FloatField':
        model_instance_field_type, = cls.inference_state.builtins_module.py__getattribute__('float')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'BinaryField':
        model_instance_field_type, = cls.inference_state.builtins_module.py__getattribute__('bytes')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'BooleanField':
        model_instance_field_type, = cls.inference_state.builtins_module.py__getattribute__('bool')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'DecimalField':
        model_instance_field_type, = cls.inference_state.import_module(('decimal',)).py__getattribute__('Decimal')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'ForeignKey':
        if isinstance(field_tree_instance, TreeInstance):
             argument_iterator = field_tree_instance._arguments.unpack()
             key, lazy_values = next(argument_iterator, (None, None))
             if key is None and lazy_values is not None:
                 # TODO: it has only one element in current state. Handle rest of elements.
                 for value in lazy_values.infer():
                     string = value.get_safe_value(default=None)
                     if value.name.string_name == 'str':
                         foreign_key_class_name = value._compiled_obj.get_safe_value()
                         # TODO: it has only one element in current state. Handle rest of elements.
                         for v in cls.parent_context.py__getattribute__(foreign_key_class_name):
                             return DjangoModelField(v, field).name
                     else:
                         return DjangoModelField(value, field).name

        raise Exception('Should be handled')

    if field_tree_instance.name.string_name == 'TimeField':
        model_instance_field_type, = cls.inference_state.import_module(('datetime',)).py__getattribute__('time')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'DurationField':
        model_instance_field_type, = cls.inference_state.import_module(('datetime',)).py__getattribute__('timedelta')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'DateField':
        model_instance_field_type, = cls.inference_state.import_module(('datetime',)).py__getattribute__('date')
        return DjangoModelField(model_instance_field_type, field).name

    if field_tree_instance.name.string_name == 'DateTimeField':
        model_instance_field_type, = cls.inference_state.import_module(('datetime',)).py__getattribute__('datetime')
        return DjangoModelField(model_instance_field_type, field).name

