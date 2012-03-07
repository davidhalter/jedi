
import parsing

class File(object):
    """
    Manages all files, that are parsed and caches them.
    Important are the params source and module_name, one of them has to
    be there.

    :param source: The source code of the file.
    :param module_name: The module name of the file.
    :param row: The row, the user is currently in. Only important for the \
    main file.
    """
    def __init__(self, source=None, module_name=None, row=None):
        self.source = source
        self.module_name = module_name
        self.row = row
        self.line_cache = None

        if not self.module_name and not self.source:
            raise AttributeError("Submit a module name or the source code")
        elif self.module_name:
            self.load_module()

        self.parser = parsing.PyFuzzyParser(source, row)

    def load_module(self):
        pass

    def get_line(self, line):
        if not self.line_cache:
            self.line_cache = self.source.split('\n')

        if 1 <= line <= len(self.line_cache):
            return self.line_cache[line-1]
        else:
            return None


def complete(source, row, colum, file_callback=None):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param row: The row to complete in.
    :type row: int
    :param col: The column to complete in.
    :type col: int
    :return: list
    :rtype: list
    """
    row = 89
    f = File(source=source, row=row)

    print 
    print 
    print f.get_line(row)
    print f.parser.user_scope
    print f.parser.user_scope.get_simple_for_line(row)
    return f.parser.user_scope.get_set_vars()
