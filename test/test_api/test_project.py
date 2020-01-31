import os

from ..helpers import get_example_dir, set_cwd, root_dir
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
    assert p in project._get_base_sys_path(inference_state)


def test_load_save_project(tmpdir):
    project = Project(tmpdir.strpath, added_sys_path=['/foo'])
    project.save()

    loaded = Project.load(tmpdir.strpath)
    assert loaded.added_sys_path == ['/foo']
