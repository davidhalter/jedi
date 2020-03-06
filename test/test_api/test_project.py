import os
import sys

import pytest

from ..helpers import get_example_dir, set_cwd, root_dir, test_dir
from jedi import Interpreter
from jedi.api import Project, get_default_project


def test_django_default_project(Script):
    dir = get_example_dir('django')

    script = Script(
        "from app import models\nmodels.SomeMo",
        path=os.path.join(dir, 'models/x.py')
    )
    c, = script.complete()
    assert c.name == "SomeModel"
    assert script._inference_state.project._django is True


def test_interpreter_project_path():
    # Run from anywhere it should be the cwd.
    dir = os.path.join(root_dir, 'test')
    with set_cwd(dir):
        project = Interpreter('', [locals()])._inference_state.project
        assert project._path == dir


def test_added_sys_path(inference_state):
    project = get_default_project()
    p = '/some_random_path'
    project.added_sys_path = [p]
    assert p in project._get_sys_path(inference_state)


def test_load_save_project(tmpdir):
    project = Project(tmpdir.strpath, added_sys_path=['/foo'])
    project.save()

    loaded = Project.load(tmpdir.strpath)
    assert loaded.added_sys_path == ['/foo']


@pytest.mark.parametrize(
    'string, full_names, kwargs', [
        ('test_load_save_project', ['test_api.test_project.test_load_save_project'], {}),
        ('test_load_savep', [], {'complete': True}),
        ('test_load_save_p', ['test_api.test_project.test_load_save_project'],
         dict(complete=True)),
        ('test_load_save_p', ['test_api.test_project.test_load_save_project'],
         dict(complete=True, all_scopes=True)),

        ('some_search_test_var', [], {}),
        ('some_search_test_var', ['test_api.test_project.test_search.some_search_test_var'],
         dict(all_scopes=True)),
        ('some_search_test_var', ['test_api.test_project.test_search.some_search_test_var'],
         dict(complete=True, all_scopes=True)),

        ('sample_int', ['helpers.sample_int'], {}),
        ('sample_int', ['helpers.sample_int'], dict(all_scopes=True)),
        ('sample_int.real', ['builtins.int.real'], {}),

        ('class sample_int.real', [], {}),
        ('function sample_int.real', ['builtins.int.real'], {}),
        ('def sample_int.real', ['builtins.int.real'], {}),
    ]
)
@pytest.mark.skipif(sys.version_info < (3, 6), reason="Ignore Python 2, because EOL")
def test_search(string, full_names, kwargs, skip_pre_python36):
    some_search_test_var = 1.0
    project = Project(test_dir)
    defs = project.search(string, **kwargs)
    assert [d.full_name for d in defs] == full_names
