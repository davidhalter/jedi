from jedi.evaluate.compiled import CompiledObject
from jedi import Script

import pytest


@pytest.mark.skipif('sys.version_info[0] < 3')  # Ellipsis does not exists in 2
@pytest.mark.parametrize('source', [
    '1 == 1',
    '1.0 == 1',
    '... == ...'
])
def test_equals(source):
    script = Script(source)
    node = script._get_module_node().children[0]
    first, = script._get_module().eval_node(node)
    assert isinstance(first, CompiledObject) and first.obj is True
