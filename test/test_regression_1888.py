"""
Regression test for https://github.com/davidhalter/jedi/issues/1888

``jedi.Script(...).complete()`` used to crash with an unhandled ``KeyError``
from parso's internal ``parser_cache`` when ``jedi.settings.fast_parser`` is
set to ``False``, for a fresh/unsaved file (``path=''``).
"""
import jedi


def test_complete_unsaved_file_without_fast_parser():
    old_fast_parser = jedi.settings.fast_parser
    jedi.settings.fast_parser = False
    try:
        # Should not raise a KeyError.
        jedi.Script(code='im', path='').complete()
    finally:
        jedi.settings.fast_parser = old_fast_parser
