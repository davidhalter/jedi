# Copyright 2004-2005 Elemental Security, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

# Modifications:
# Copyright 2006 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

__all__ = ["Driver", "load_grammar"]


import os
import sys
import logging
import io

from . import pgen
from . import grammar
from . import parse
from . import token
from . import tokenize


class Driver(object):
    def __init__(self, grammar, convert, error_recovery, logger=None):
        self.grammar = grammar
        if logger is None:
            logger = logging.getLogger()
        self.logger = logger
        self.convert = convert
        self.error_recovery = error_recovery

    def parse_tokens(self, tokens):
        """Parse a series of tokens and return the syntax tree."""
        # XXX Move the prefix computation into a wrapper around tokenize.
        p = parse.Parser(self.grammar, self.convert, self.error_recovery)
        lineno = 1
        column = 0
        type = value = start = end = line_text = None
        prefix = ""
        for quintuple in tokens:
            type, value, start, end, line_text = quintuple
            if start != (lineno, column):
                assert (lineno, column) <= start, ((lineno, column), start)
                s_lineno, s_column = start
                if lineno < s_lineno:
                    prefix += "\n" * (s_lineno - lineno)
                    lineno = s_lineno
                    column = 0
                if column < s_column:
                    prefix += line_text[column:s_column]
                    column = s_column
            if type in (tokenize.COMMENT, tokenize.NL):  # NL != NEWLINE
                prefix += value
                lineno, column = end
                if value.endswith("\n"):
                    lineno += 1
                    column = 0
                continue
            if type == token.OP:
                type = grammar.opmap[value]
            #self.logger.debug("%s %r (prefix=%r)", token.tok_name[type], value, prefix)
            if p.addtoken(type, value, (prefix, start)):
                break
            prefix = ""
            lineno, column = end
            if value.endswith("\n"):
                lineno += 1
                column = 0
        else:
            # We never broke out -- EOF is too soon (how can this happen???)
            raise parse.ParseError("incomplete input",
                                   type, value, (prefix, start))
        return p.rootnode

    def parse_string(self, text):
        """Parse a string and return the syntax tree."""
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return self.parse_tokens(tokens)


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
