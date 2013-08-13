import jedi
import sys
from os.path import dirname, join

def test_namespace_package():
    sys.path.insert(0, join(dirname(__file__), 'namespace_package/ns1'))
    sys.path.insert(1, join(dirname(__file__), 'namespace_package/ns2'))
    try:
        assert jedi.Script('from pkg import ns1_file').goto_definitions()
        assert jedi.Script('from pkg import ns2_file').goto_definitions()
        assert not jedi.Script('from pkg import ns3_file').goto_definitions()

        completions = jedi.Script('from pkg import ').completions()
        names = [str(c.name) for c in completions]  # str because of unicode
        compare = ['foo', 'ns1_file', 'ns1_folder', 'ns2_folder', 'ns2_file']
        # must at least contain these items, other items are not important
        assert not (set(compare) - set(names))
    finally:
        sys.path.pop(0)
        sys.path.pop(0)
