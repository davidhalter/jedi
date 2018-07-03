"""The client for Jedi's subprocess protocol.

It gets started from :py:func:`_CompiledSubprocess._process`, which sets
``PYTHONPATH``, so that parso can be found.
"""
import sys

from jedi.evaluate.compiled import subprocess

# Retrieve the pickle protocol.
pickle_protocol = int(sys.argv[1])
# And finally start the client.
subprocess.Listener(pickle_protocol).listen()
