from jedi.evaluate.compiled import CompiledObject

import pytest


@pytest.mark.parametrize('source', [
    '1 == 1',
    '1.0 == 1',
    '... == ...'
])
def test_equals(Script, environment, source):
    if environment.version_info.major < 3:
        pytest.skip("Ellipsis does not exists in 2")
    script = Script(source)
    node = script._module_node.children[0]
    first, = script._get_module().eval_node(node)
    assert isinstance(first, CompiledObject) and first.get_safe_value() is True
