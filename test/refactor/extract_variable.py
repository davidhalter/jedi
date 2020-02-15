# -------------------------------------------------- simple-1
def test():
    #? 35 text {'new_name': 'a'}
    return test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 35 text {'new_name': 'a'}
    a = (30 + b, c) + 1
    return test(100, a)
# -------------------------------------------------- simple-2
def test():
    #? 25 text {'new_name': 'a'}
    return test(100, (30 + b, c) + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 25 text {'new_name': 'a'}
    a = 30 + b
    return test(100, (a, c) + 1)
# -------------------------------------------------- multiline-1
def test():
    #? 30 text {'new_name': 'x'}
    return test(1, (30 + b, c) 
                            + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 30 text {'new_name': 'x'}
    x = (30 + b, c) 
                                + 1
    return test(1, x)
# -------------------------------------------------- multiline-2
def test():
    #? 25 text {'new_name': 'x'}
    return test(1, (30 + b, c) 
                            + 1)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
def test():
    #? 25 text {'new_name': 'x'}
    x = 30 + b
    return test(1, (x, c) 
                            + 1)
