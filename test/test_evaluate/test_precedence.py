from jedi.parser import load_grammar, Parser
from jedi.evaluate import Evaluator
from jedi.evaluate.compiled import CompiledObject

import pytest


@pytest.mark.skipif('sys.version_info[0] < 3')  # Ellipsis does not exists in 2
@pytest.mark.parametrize('source', [
    '1 == 1',
    '1.0 == 1',
    '... == ...'
])
def test_equals(source):
    evaluator = Evaluator(load_grammar())
    node = Parser(load_grammar(), source, 'eval_input').get_parsed_node()
    results = evaluator.eval_element(node)
    assert len(results) == 1
    first = results.pop()
    assert isinstance(first, CompiledObject) and first.obj is True
