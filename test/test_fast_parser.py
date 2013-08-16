import jedi

def test_add_to_end():
    """
    fast_parser doesn't parse everything again. It just updates with the
    help of caches, this is an example that didn't work.
    """

    a = """
class Abc():
    def abc(self):
        self.x = 3

class Two(Abc):
    def h(self):
        self.
"""  #       ^ here is the first completion

    b = "    def h(self):\n" \
        "        self."
    assert jedi.Script(a, 8, 13, 'example.py').completions()
    assert  jedi.Script(a + b, path='example.py').completions()
