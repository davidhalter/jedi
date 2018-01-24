import os

from ..helpers import get_example_dir


def test_django_default_project(Script):
    dir = get_example_dir('django')

    script = Script(
        "from app import models\nmodels.SomeMo",
        path=os.path.join(dir, 'models/x.py')
    )
    c, = script.completions()
    assert c.name == "SomeModel"
    assert script._project._django is True
