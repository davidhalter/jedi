import datetime
import decimal
import uuid

from django.db import models
from django.contrib.auth.models import User


class Tag(models.Model):
    tag_name = models.CharField()


class Category(models.Model):
    category_name = models.CharField()


class AttachedData(models.Model):
    extra_data = models.TextField()


class BusinessModel(models.Model):
    attached_o2o = models.OneToOneField(AttachedData)

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
    ip_address_field = models.GenericIPAddressField()
    url_field = models.URLField()
    float_field = models.FloatField()
    binary_field = models.BinaryField()
    boolean_field = models.BooleanField()
    decimal_field = models.DecimalField()
    time_field = models.TimeField()
    duration_field = models.DurationField()
    date_field = models.DateField()
    date_time_field = models.DateTimeField()
    uuid_field = models.UUIDField()
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
#? str()
model_instance.ip_address_field
#? str()
model_instance.url_field
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
#? uuid.UUID()
model_instance.uuid_field

#! ['attached_o2o = models.OneToOneField(AttachedData)']
model_instance.attached_o2o
#! ['extra_data = models.TextField()']
model_instance.attached_o2o.extra_data
#? AttachedData()
model_instance.attached_o2o
#? str()
model_instance.attached_o2o.extra_data

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
#?
model_instance.category_fk3
#?
model_instance.category_fk4
#?
model_instance.category_fk5

#? models.manager.RelatedManager()
model_instance.tags_m2m
#? Tag()
model_instance.tags_m2m.get()
#? ['add']
model_instance.tags_m2m.add

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
#? int()
model_instance.objects.update(x='')
#? BusinessModel()
model_instance.objects.create()

# -----------------
# Inheritance
# -----------------

class Inherited(BusinessModel):
    text_field = models.IntegerField()
    new_field = models.FloatField()

inherited = Inherited()
#? int()
inherited.text_field
#? str()
inherited.char_field
#? float()
inherited.new_field

#? str()
inherited.category_fk2.category_name
#? str()
inherited.objects.get().char_field
#? int()
inherited.objects.get().text_field
#? float()
inherited.objects.get().new_field

# -----------------
# Django Auth
# -----------------

#? str()
User().email
#? str()
User.objects.get().email

# -----------------
# values & values_list (dave is too lazy to implement it)
# -----------------

#?
model_instance.objects.values_list('char_field')[0]
#? dict()
model_instance.objects.values('char_field')[0]
#?
model_instance.objects.values('char_field')[0]['char_field']
