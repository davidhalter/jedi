"""
Tests ``from __future__ import absolute_import`` (only important for
Python 2.X)
"""
from jedi import Project
from .. import helpers


def test_can_complete_when_shadowing(Script):
    path = helpers.get_example_dir('absolute_import', 'unittest.py')
    script = Script(path=path, project=Project(helpers.get_example_dir('absolute_import')))
    assert script.complete()
