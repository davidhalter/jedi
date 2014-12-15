# Copyright 2004-2005 Elemental Security, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

# Modifications:
# Copyright 2006 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

__all__ = ["load_grammar"]


import os
import sys
import logging

from . import pgen
from . import grammar


def load_grammar(grammar_path="grammar.txt", pickle_path=None,
                 save=True, force=False, logger=None):
    """Load the grammar (maybe from a pickle)."""
    if logger is None:
        logger = logging.getLogger()
    if pickle_path is None:
        head, tail = os.path.splitext(grammar_path)
        if tail == ".txt":
            tail = ""
        pickle_path = head + tail + ".".join(map(str, sys.version_info)) + ".pickle"
    if force or not _newer(pickle_path, grammar_path):
        logger.info("Generating grammar tables from %s", grammar_path)
        g = pgen.generate_grammar(grammar_path)
        # the pickle files mismatch, when built on different architectures.
        # don't save these for now. An alternative solution might be to
        # include the multiarch triplet into the file name
        if False:
            logger.info("Writing grammar tables to %s", pickle_path)
            try:
                g.dump(pickle_path)
            except OSError as e:
                logger.info("Writing failed:" + str(e))
    else:
        g = grammar.Grammar()
        g.load(pickle_path)
    return g


def _newer(a, b):
    """Inquire whether file a was written since file b."""
    if not os.path.exists(a):
        return False
    if not os.path.exists(b):
        return True
    return os.path.getmtime(a) >= os.path.getmtime(b)
