# --- a
def test():
    #? 25 a
    return test(1, (30 + b, c) + 1)

# +++
def test():
    a = (30 + b, c) + 1
    return test(a)

# --- multiline
def test():
    return test(1, (30 + b, c) + 1)
# +++
def test():
    a = (30 + b, c) + 1
    return test(a)
