"""
Test completions from *.pyc files:

 - generated a dummy python module
 - compile the dummy module to generate a *.pyc
 - delete the pure python dummy module
 - try jedi on the generated *.pyc
"""
import os
import compileall
import jedi

SRC = """class Foo:
    pass

class Bar:
    pass
"""


def generate_pyc():
    with open("dummy.py", 'w') as f:
        f.write(SRC)
    compileall.compile_file("dummy.py")
    os.remove("dummy.py")


def test_pyc():
    """
    The list of completion must be greater than 2.
    """
    generate_pyc()
    s = jedi.Script("import dummy; dummy.")
    assert len(s.completions()) >= 2


if __name__ == "__main__":
    test_pyc()
