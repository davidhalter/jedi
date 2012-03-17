import parsing

def get_names_for_scope(scope):
    """ Get all completions possible for the current scope. """
    compl = []
    start_scope = scope
    while scope:
        # class variables/functions are only availabe
        if not isinstance(scope, parsing.Class) or scope == start_scope:
            compl += scope.get_set_vars()
        scope = scope.parent
    return compl


# default: name in scope
# point: chaining
# execution: -> eval returns default & ?
def follow_statement(scope, stmt):
    arr = stmt.get_assignment_calls()
    return call


def follow_array(scope, array):
    return


def follow_path(scope, path):
    """
    Follow a path of python names.
    recursive!
    :returns: list(Scope)
    """
    compl = get_names_for_scope(scope)
    print path, compl

    path = list(path)
    name = path.pop(0)
    scopes = []

    # make the full comparison, because the names have to match exactly
    compl = [c for c in compl if [name] == list(c.names)]
    # TODO differentiate between the different comp input (some are overridden)
    for c in compl:
        p_class = c.parent.__class__
        if p_class == parsing.Class or p_class == parsing.Scope:
            scopes.append(c.parent)
        #elif p_class == parsing.Function:
        elif p_class == parsing.Statement:
            print 'state', c.parent.token_list, c.parent.get_assignment_calls()
            pass
        else:
            print 'error follow_path:', p_class, repr(c.parent)

    if path:
        new_scopes = []
        for s in tuple(scopes):
            new_scopes += follow_path(s, tuple(path))
        scopes = new_scopes
    return set(scopes)

def _parseassignment(self):
    """ TODO remove or replace, at the moment not used """
    assign = ''
    token_type, tok, indent = self.next()
    if token_type == tokenize.STRING or tok == 'str':
        return '""'
    elif tok == '(' or tok == 'tuple':
        return '()'
    elif tok == '[' or tok == 'list':
        return '[]'
    elif tok == '{' or tok == 'dict':
        return '{}'
    elif token_type == tokenize.NUMBER:
        return '0'
    elif tok == 'open' or tok == 'file':
        return 'file'
    elif tok == 'None':
        return '_PyCmplNoType()'
    elif tok == 'type':
        return 'type(_PyCmplNoType)'  # only for method resolution
    else:
        assign += tok
        level = 0
        while True:
            token_type, tok, indent = self.next()
            if tok in ('(', '{', '['):
                level += 1
            elif tok in (']', '}', ')'):
                level -= 1
                if level == 0:
                    break
            elif level == 0:
                if tok in (';', '\n'):
                    break
                assign += tok
    return "%s" % assign

def dbg(*args):
    if debug_function:
        debug_function(*args)


debug_function = None
