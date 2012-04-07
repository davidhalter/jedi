import tokenize

import parsing
import evaluate
import modules
import debug

__all__ = ['complete', 'complete_test', 'set_debug_function']


class ParserError(LookupError):
    """ The exception that is thrown if some handmade parser fails. """
    pass


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
                line = line[:column - 1]
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

    # print a debug.dbg title
    debug.dbg('complete_scope', scope)

    try:
        path = f.get_row_path(column)
        print path
        debug.dbg('completion_path', path)
    except ParserError as e:
        path = []
        debug.dbg(e)

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

    try:
        path = f.get_row_path(column)
        print path
        debug.dbg('completion_path', path)
    except ParserError as e:
        path = []
        debug.dbg(e)

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
