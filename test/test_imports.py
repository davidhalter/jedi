import sys

import pytest

from jedi._compatibility import find_module_py33


@pytest.mark.skipif('sys.version_info <= (3,2)')
def test_find_module_py33():
    """Needs to work like the old find_module."""
    print(find_module_py33('_io'))
    assert find_module_py33('_io') == (None, '_io', False)
