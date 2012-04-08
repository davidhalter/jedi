import tokenize
import re

import parsing
import evaluate
import modules
import debug

__all__ = ['complete', 'get_completion_parts', 'complete_test', 'set_debug_function']


class FileWithCursor(modules.File):
    """
    Manages all files, that are parsed and caches them.
    Important are the params source and module_name, one of them has to
    be there.

    :param source: The source code of the file.
    :param module_name: The module name of the file.
    :param row: The row, the user is currently in. Only important for the \
    main file.
    """
    def __init__(self, module_name, source, row):
        super(FileWithCursor, self).__init__(module_name, source)
        self.row = row

        # this two are only used, because there is no nonlocal in Python 2
        self._row_temp = None
        self._relevant_temp = None

        self._parser = parsing.PyFuzzyParser(source, row)

    def get_row_path(self, column):
        """ Get the path under the cursor. """
        self._is_first = True
        def fetch_line():
            line = self.get_line(self._row_temp)
            if self._is_first:
                self._is_first = False
                line = line[:column]
            else:
                line = line + '\n'
            # add lines with a backslash at the end
            while self._row_temp > 1:
                self._row_temp -= 1
                last_line = self.get_line(self._row_temp)
                if last_line and last_line[-1] == '\\':
                    line = last_line[:-1] + ' ' + line
                else:
                    break
            return line[::-1]

        self._row_temp = self.row

        force_point = False
        open_brackets = ['(', '[', '{']
        close_brackets = [')', ']', '}']

        gen = tokenize.generate_tokens(fetch_line)
        # TODO can happen: raise TokenError, ("EOF in multi-line statement"
        string = ''
        level = 0
        for token_type, tok, start, end, line in gen:
            #print token_type, tok, line
            if level > 0:
                if tok in close_brackets:
                    level += 1
                if tok in open_brackets:
                    level -= 1
            elif tok == '.':
                force_point = False
            elif force_point:
                if tok != '.':
                    # it is reversed, therefore a number is getting recognized
                    # as a floating point number
                    if not (token_type == tokenize.NUMBER and tok[0] == '.'):
                        #print 'break2', token_type, tok
                        break
            elif tok in close_brackets:
                level += 1
            elif token_type in [tokenize.NAME, tokenize.STRING]:
                force_point = True
            elif token_type == tokenize.NUMBER:
                pass
            else:
                #print 'break', token_type, tok
                break

            string += tok

        return string[::-1]

    def get_line(self, line):
        if not self._line_cache:
            self._line_cache = self.source.split('\n')

        try:
            return self._line_cache[line - 1]
        except IndexError:
            raise StopIteration()


class Completion(object):
    def __init__(self, name, needs_dot, like_name_length):
        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length

    @property
    def complete(self):
        dot = '.' if self.needs_dot else ''
        return dot + self.name.names[-1][self.like_name_length:]

    @property
    def description(self):
        return str(self.name.parent)

    @property
    def help(self):
        try:
            return str(self.name.parent.docstr)
        except:
            return ''

    @property
    def type(self):
        return '' # type(self.name)

    def __str__(self):
        return self.name.names[-1]


def get_completion_parts(path):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
    return match.groups()

def complete(source, row, column, file_callback=None):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param row: The row to complete in.
    :type row: int
    :param col: The column to complete in.
    :type col: int
    :return: list of completion objects
    :rtype: list
    """
    f = FileWithCursor('__main__', source=source, row=row)
    scope = f.parser.user_scope
    path = f.get_row_path(column)
    debug.dbg('completion_start: %s in %s' % (path, scope))

    # just parse one statement, take it and evaluate it
    path, dot, like = get_completion_parts(path)
    r = parsing.PyFuzzyParser(path)
    try:
        stmt = r.top.statements[0]
    except IndexError:
        completions = evaluate.get_names_for_scope(scope)
    else:
        scopes = evaluate.follow_statement(stmt, scope)

        completions = []
        debug.dbg('possible scopes', scopes)
        for s in scopes:
            completions += s.get_defined_names()

    print repr(path), repr(dot), repr(like), row, column
    print len(completions)
    needs_dot = not dot and path
    completions = [Completion(c, needs_dot, len(like)) for c in completions
                            if c.names[-1].lower().startswith(like.lower())]
    print 'nr2', len(completions)

    return completions


def complete_test(source, row, column, file_callback=None):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param row: The row to complete in.
    :type row: int
    :param col: The column to complete in.
    :type col: int
    :return: list of completion objects
    :rtype: list
    """
    # !!!!!!! this is the old version and will be deleted soon !!!!!!!
    row = 150
    column = 200
    f = FileWithCursor('__main__', source=source, row=row)
    scope = f.parser.user_scope

    # print a debug.dbg title
    debug.dbg()
    debug.dbg('-' * 70)
    debug.dbg(' ' * 62 + 'complete')
    debug.dbg('-' * 70)
    debug.dbg('complete_scope', scope)

    path = f.get_row_path(column)
    print path
    debug.dbg('completion_path', path)

    result = []
    if path and path[0]:
        # just parse one statement
        #debug.ignored_modules = ['builtin']
        r = parsing.PyFuzzyParser(path)
        #debug.ignored_modules = ['parsing', 'builtin']
        #print 'p', r.top.get_code().replace('\n', r'\n'), r.top.statements[0]
        scopes = evaluate.follow_statement(r.top.statements[0], scope)

        #name = path.pop() # use this later
        compl = []
        debug.dbg('possible scopes')
        for s in scopes:
            compl += s.get_defined_names()

        #else:
        #    compl = evaluate.get_names_for_scope(scope)

        debug.dbg('possible-compl', compl)

        # make a partial comparison, because the other options have to
        # be returned as well.
        result = compl
        #result = [c for c in compl if name in c.names[-1]]

    return result


def set_debug_function(func_cb):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb
