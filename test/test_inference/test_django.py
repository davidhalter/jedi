import pytest
import datetime
import decimal

source_tpl_basic_types = '''
from django.db import models

class BusinessModel(models.Model):
    {0} = {1}

p1 = BusinessModel()
p1_field = p1.{0}
p1_field.'''


source_tpl_foreign_key = '''
from django.db import models

class Category(models.Model):
    category_name = models.CharField()

class BusinessModel(models.Model):
    category = models.ForeignKey(Category)

p1 = BusinessModel()
p1_field = p1.category
p1_field.'''


@pytest.mark.parametrize('field_name, field_model_type, expected_fields', [
    ('integer_field', 'models.IntegerField()', dir(int)),
    ('big_integer_field', 'models.BigIntegerField()', dir(int)),
    ('positive_integer_field', 'models.PositiveIntegerField()', dir(int)),
    ('small_integer_field', 'models.SmallIntegerField()', dir(int)),
    ('char_field', 'models.CharField()', dir(str)),
    ('text_field', 'models.TextField()', dir(str)),
    ('email_field', 'models.EmailField()', dir(str)),
    ('float_field', 'models.FloatField()', dir(float)),
    ('binary_field', 'models.BinaryField()', dir(bytes)),
    ('boolean_field', 'models.BooleanField()', dir(bool)),
    ('decimal_field', 'models.DecimalField()', dir(decimal.Decimal)),
    ('time_field', 'models.TimeField()', dir(datetime.time)),
    ('duration_field', 'models.DurationField()', dir(datetime.timedelta)),
    ('date_field', 'models.DateField()', dir(datetime.date)),
    ('date_time_field', 'models.DateTimeField()', dir(datetime.datetime)),
])
def test_basic_types(
    field_name,
    field_model_type,
    expected_fields,
    Script,
):
    source = source_tpl_basic_types.format(field_name, field_model_type)
    result = Script(source).complete()
    result = {x.name for x in result}
    expected_fields_public = [x for x in expected_fields if x[0] != '_']
    for field in expected_fields_public:
        assert field in result


def test_foreign_key(Script):
    result = Script(source_tpl_foreign_key).complete()
    result = {x.name for x in result}
    assert 'category_name' in result
