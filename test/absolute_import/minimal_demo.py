import jedi

filename = "unittest.py"
with open(filename) as f:
    lines = f.readlines()
src = "".join(lines)
script = jedi.Script(src, len(lines), len(lines[1]), filename)

print script.completions()
