"""
This is not a plugin, this is just the place were plugins are registered.
"""

from jedi.plugins import stdlib
from jedi.plugins import flask
from jedi.plugins import django
from jedi.plugins import plugin_manager
from jedi.plugins import pytest


plugin_manager.register(stdlib, flask, pytest, django)
