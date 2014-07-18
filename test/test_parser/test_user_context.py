import jedi


def test_form_feed_characters():
    s = "\f\nclass Test(object):\n    pass"
    jedi.Script(s, line=2, column=18).call_signatures()
