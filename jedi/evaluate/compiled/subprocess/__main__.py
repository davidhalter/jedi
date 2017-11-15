import sys
import os

# Get the path to jedi.
_d = os.path.dirname
_jedi_path = _d(_d(_d(_d(_d(__file__)))))
_parso_path = sys.argv[1]

# This is kind of stupid. We actually don't want to modify the sys path but
# simply import something from a specific location.
sys.path[0:0] = [_jedi_path, _parso_path]
from jedi.evaluate.compiled import subprocess
sys.path[0:2] = []

subprocess.Listener().listen()
