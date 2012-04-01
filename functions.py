import re

import parsing
import evaluate
import modules
import debug

__all__ = ['complete', 'set_debug_function']


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
        def fetch_line(with_column=False):
            line = self.get_line(self._row_temp)
            if with_column:
                self._relevant_temp = line[:column - 1]
            else:
                self._relevant_temp += line + ' ' + self._relevant_temp
            while self._row_temp > 1:
                self._row_temp -= 1
                last_line = self.get_line(self._row_temp)
                if last_line and last_line[-1] == '\\':
                    self._relevant_temp = last_line[:-1] + self._relevant_temp
                else:
                    break

        def fetch_name(is_first):
            """
            :param is_first: This means, that there can be a point \
            (which is a name separator) directly. There is no need for a name.
            :type is_first: str
            :return: The list of names and an is_finished param.
            :rtype: (list, bool)

            :raises: ParserError
            """
            def get_char():
                self._relevant_temp, char = self._relevant_temp[:-1], \
                                            self._relevant_temp[-1]
                return char

            whitespace = [' ', '\n', '\r', '\\']
            open_brackets = ['(', '[', '{']
            close_brackets = [')', ']', '}']
            is_word = lambda char: re.search('\w', char)
            name = ''
            force_point = False
            force_no_brackets = False
            is_finished = False
            while True:
                try:
                    char = get_char()
                except IndexError:
                    is_finished = True
                    break

                if force_point:
                    if char in whitespace:
                        continue
                    elif char != '.':
                        is_finished = True
                        break

                if char == '.':
                    if not is_first and not name:
                        raise ParserError('No name after point (@%s): %s'
                                            % (self._row_temp,
                                                self._relevant_temp + char))
                    break
                elif char in whitespace:
                    if is_word(name[0]):
                        force_point = True
                elif char in close_brackets:
                    # TODO strings are not looked at here, they are dangerous!
                    # handle them!
                    # TODO handle comments
                    if force_no_brackets:
                        is_finished = True
                        break
                    level = 1
                    name = char + name
                    while True:
                        try:
                            char = get_char()
                        except IndexError:
                            while not self._relevant_temp:
                                # TODO can raise an exception, when there are
                                # no more lines
                                fetch_line()
                            char = get_char()
                        if char in close_brackets:
                            level += 1
                        elif char in open_brackets:
                            level -= 1
                        name = char + name
                        if level == 0:
                            break
                elif is_word(char):
                    # TODO handle strings -> "asdf".join([1,2])
                    name = char + name
                    force_no_brackets = True
                else:
                    is_finished = True
                    break
            return name, is_finished

        self._row_temp = self.row
        self._relevant_temp = ''
        fetch_line(True)

        names = []
        is_finished = False
        while not is_finished:
            # do this not with tokenize, because it might fail
            # due to single line processing
            name, is_finished = fetch_name(not bool(names))
            names.insert(0, name)
        return names


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
    row = 84
    column = 17

    row = 140
    row = 148
    column = 200
    f = FileWithCursor('__main__', source=source, row=row)
    scope = f.parser.user_scope

    # print a debug.dbg title
    debug.dbg()
    debug.dbg('-' * 70)
    debug.dbg(' ' * 62 + 'complete')
    debug.dbg('-' * 70)
    print 'complete_scope', scope
    print 'user_scope', f.parser.user_scope.get_simple_for_line(row)

    try:
        path = f.get_row_path(column)
    except ParserError as e:
        path = []
        debug.dbg(e)

    result = []
    if path and path[0]:
        # just parse one statement
        r = parsing.PyFuzzyParser(".".join(path))
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
