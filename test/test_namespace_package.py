import jedi
import sys

def test_namespace_package():
    sys.path.insert(0, 'namespace_package/ns1')
    sys.path.insert(1, 'namespace_package/ns2')
    try:
        assert jedi.Script('from pkg import ns1_file').goto_definitions()
        assert jedi.Script('from pkg import ns2_file').goto_definitions()
        assert not jedi.Script('from pkg import ns3_file').goto_definitions()

        completions = jedi.Script('from pkg import ').completions()
        names = [c.name for c in completions]
        assert names == ['foo', 'ns1_file', 'ns1_folder', 'ns2_folder', 'ns2_file']
    finally:
        sys.path.pop(0)
        sys.path.pop(0)
