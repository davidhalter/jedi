import datetime
import decimal

from django.db import models
from django.contrib.auth.models import User


#? str()
User().email


class Tag(models.Model):
    tag_name = models.CharField()


class Category(models.Model):
    category_name = models.CharField()


class BusinessModel(models.Model):
    category_fk = models.ForeignKey(Category)
    category_fk2 = models.ForeignKey('Category')
    category_fk3 = models.ForeignKey(1)
    category_fk4 = models.ForeignKey('models')
    category_fk5 = models.ForeignKey()

    integer_field = models.IntegerField()
    big_integer_field = models.BigIntegerField()
    positive_integer_field = models.PositiveIntegerField()
    small_integer_field = models.SmallIntegerField()
    char_field = models.CharField()
    text_field = models.TextField()
    email_field = models.EmailField()
    float_field = models.FloatField()
    binary_field = models.BinaryField()
    boolean_field = models.BooleanField()
    decimal_field = models.DecimalField()
    time_field = models.TimeField()
    duration_field = models.DurationField()
    date_field = models.DateField()
    date_time_field = models.DateTimeField()
    tags_m2m = models.ManyToManyField(Tag)

    unidentifiable = NOT_FOUND

# -----------------
# Model attribute inference
# -----------------

model_instance = BusinessModel()
#? int()
model_instance.integer_field
#? int()
model_instance.big_integer_field
#? int()
model_instance.positive_integer_field
#? int()
model_instance.small_integer_field
#? str()
model_instance.char_field
#? str()
model_instance.text_field
#? str()
model_instance.email_field
#? float()
model_instance.float_field
#? bytes()
model_instance.binary_field
#? bool()
model_instance.boolean_field
#? decimal.Decimal()
model_instance.decimal_field
#? datetime.time()
model_instance.time_field
#? datetime.timedelta()
model_instance.duration_field
#? datetime.date()
model_instance.date_field
#? datetime.datetime()
model_instance.date_time_field

#! ['category_fk = models.ForeignKey(Category)']
model_instance.category_fk
#! ['category_name = models.CharField()']
model_instance.category_fk.category_name
#? Category()
model_instance.category_fk
#? str()
model_instance.category_fk.category_name
#? Category()
model_instance.category_fk2
#? str()
model_instance.category_fk2.category_name
#? models.ForeignKey()
model_instance.category_fk3
#?
model_instance.category_fk4
#? models.ForeignKey()
model_instance.category_fk5

#? models.ManyToManyField()
model_instance.tags_m2m

#?
model_instance.unidentifiable
#! ['unidentifiable = NOT_FOUND']
model_instance.unidentifiable

# -----------------
# Queries
# -----------------

#? models.query.QuerySet.filter
model_instance.objects.filter
#? BusinessModel() None
model_instance.objects.filter().first()
#? str()
model_instance.objects.get().char_field
