This directory contains pre-compiled extensions modules used to test completions
for compiled modules on Travis-CI (Ubuntu 12.04 64bit).

To build the extensions modules, run::

    python setup.py build_ext -i


Then move the compiled modules to their testing package ( ./**compiledXX**, where XX is the
python version used to run setup.py).