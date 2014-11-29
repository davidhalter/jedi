"""
The ``Parser`` tries to convert the available Python code in an easy to read
format, something like an abstract syntax tree. The classes who represent this
tree, are sitting in the :mod:`jedi.parser.tree` module.

The Python module ``tokenize`` is a very important part in the ``Parser``,
because it splits the code into different words (tokens).  Sometimes it looks a
bit messy. Sorry for that! You might ask now: "Why didn't you use the ``ast``
module for this? Well, ``ast`` does a very good job understanding proper Python
code, but fails to work as soon as there's a single line of broken code.

There's one important optimization that needs to be known: Statements are not
being parsed completely. ``Statement`` is just a representation of the tokens
within the statement. This lowers memory usage and cpu time and reduces the
complexity of the ``Parser`` (there's another parser sitting inside
``Statement``, which produces ``Array`` and ``Call``).
"""
import logging
import os

from jedi._compatibility import next
from jedi import common
from jedi.parser import tree as pt
from jedi.parser import tokenize
from jedi.parser import pgen2

OPERATOR_KEYWORDS = 'and', 'for', 'if', 'else', 'in', 'is', 'lambda', 'not', 'or'
# Not used yet. In the future I intend to add something like KeywordStatement
STATEMENT_KEYWORDS = 'assert', 'del', 'global', 'nonlocal', 'raise', \
    'return', 'yield', 'pass', 'continue', 'break'


_loaded_grammars = {}


def load_grammar(file='grammar3.4'):
    global _loaded_grammars
    path = os.path.join(os.path.dirname(__file__), file) + '.txt'
    try:
        return _loaded_grammars[path]
    except KeyError:
        return _loaded_grammars.setdefault(path, pgen2.load_grammar(path))


class ErrorStatement(object):
    def __init__(self, stack, next_token, next_start_pos):
        self.stack = stack
        self.next_token = next_token
        self.next_start_pos = next_start_pos

    @property
    def first_pos(self):
        first_type, nodes = self.stack[0]
        return nodes[0].start_pos

    @property
    def first_type(self):
        first_type, nodes = self.stack[0]
        return first_type


class Parser(object):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of different scopes.

    :param grammar: The grammar object of pgen2. Loaded by load_grammar.
    :param source: The codebase for the parser. Must be unicode.
    :param module_path: The path of the module in the file system, may be None.
    :type module_path: str
    :param top_module: Use this module as a parent instead of `self.module`.
    """
    def __init__(self, grammar, source, module_path=None, tokenizer=None):
        """
        This is the way I imagine a parser describing the init function
        """

        if not source.endswith('\n'):
            source += '\n'

        self._ast_mapping = {
            'expr_stmt': pt.ExprStmt,
            'classdef': pt.Class,
            'funcdef': pt.Function,
            'file_input': pt.SubModule,
            'import_name': pt.ImportName,
            'import_from': pt.ImportFrom,
            'break_stmt': pt.KeywordStatement,
            'continue_stmt': pt.KeywordStatement,
            'return_stmt': pt.ReturnStmt,
            'raise_stmt': pt.KeywordStatement,
            'yield_expr': pt.YieldExpr,
            'del_stmt': pt.KeywordStatement,
            'pass_stmt': pt.KeywordStatement,
            'global_stmt': pt.GlobalStmt,
            'nonlocal_stmt': pt.KeywordStatement,
            'assert_stmt': pt.KeywordStatement,
            'if_stmt': pt.IfStmt,
            'with_stmt': pt.WithStmt,
            'for_stmt': pt.ForStmt,
            'while_stmt': pt.WhileStmt,
            'try_stmt': pt.TryStmt,
            'comp_for': pt.CompFor,
            'decorator': pt.Decorator,
        }

        self.global_names = []

        # TODO do print absolute import detection here.
        #try:
        #    del python_grammar_no_print_statement.keywords["print"]
        #except KeyError:
        #    pass  # Doesn't exist in the Python 3 grammar.


        #if self.options["print_function"]:
        #    python_grammar = pygram.python_grammar_no_print_statement
        #else:
        # When this is True, the refactor*() methods will call write_file() for
        # files processed even if they were not changed during refactoring. If
        # and only if the refactor method's write parameter was True.
        self.used_names = {}
        self.scope_names_stack = [{}]
        self.error_statement_stacks = []
        logger = logging.getLogger("Jedi-Parser")
        if False:
            d = pgen2.Driver(grammar, self.convert_node,
                             self.convert_leaf, self.error_recovery, logger=logger)
            self.module = d.parse_string(source).get_parent_until()
        else:
            p = pgen2.parse.Parser(grammar, self.convert_node, self.convert_leaf,
                                   self.error_recovery)
            tokenizer = tokenizer or tokenize.source_tokens(source)
            self.module = p.parse(p.tokenize(self._tokenize(tokenizer)))

        self.module.used_names = self.used_names
        self.module.path = module_path
        self.module.set_global_names(self.global_names)
        self.module.error_statement_stacks = self.error_statement_stacks
        self.grammar_symbols = grammar.number2symbol

    def convert_node(self, grammar, type, children):
        """
        Convert raw node information to a Node instance.

        This is passed to the parser driver which calls it whenever a reduction of a
        grammar rule produces a new complete node, so that the tree is build
        strictly bottom-up.
        """
        symbol = grammar.number2symbol[type]
        try:
            new_node = self._ast_mapping[symbol](children)
        except KeyError:
            new_node = pt.Node(symbol, children)

        # We need to check raw_node always, because the same node can be
        # returned by convert multiple times.
        if symbol == 'global_stmt':
            self.global_names += new_node.get_defined_names()
        elif isinstance(new_node, (pt.ClassOrFunc, pt.Module)) \
                and symbol in ('funcdef', 'classdef', 'file_input'):
            # scope_name_stack handling
            scope_names = self.scope_names_stack.pop()
            if isinstance(new_node, pt.ClassOrFunc):
                n = new_node.name
                scope_names[n.value].remove(n)
                # Set the func name of the current node
                arr = self.scope_names_stack[-1].setdefault(n.value, [])
                arr.append(n)
            new_node.names_dict = scope_names
        elif isinstance(new_node, pt.CompFor):
            # The name definitions of comprehenions shouldn't be part of the
            # current scope. They are part of the comprehension scope.
            for n in new_node.get_defined_names():
                self.scope_names_stack[-1][n.value].remove(n)
        return new_node

    def convert_leaf(self, grammar, type, value, prefix, start_pos):
        #print('leaf', value, pytree.type_repr(type))
        if type == tokenize.NAME:
            if value in grammar.keywords:
                if value in ('def', 'class'):
                    self.scope_names_stack.append({})

                return pt.Keyword(value, start_pos, prefix)
            else:
                name = pt.Name(value, start_pos, prefix)
                # Keep a listing of all used names
                arr = self.used_names.setdefault(name.value, [])
                arr.append(name)
                arr = self.scope_names_stack[-1].setdefault(name.value, [])
                arr.append(name)
                return name
        elif type == tokenize.STRING:
            return pt.String(value, start_pos, prefix)
        elif type == tokenize.NUMBER:
            return pt.Number(value, start_pos, prefix)
        elif type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            return pt.Whitespace(value, start_pos, prefix)
        else:
            return pt.Operator(value, start_pos, prefix)

    def error_recovery(self, grammar, stack, typ, value, start_pos, prefix,
                       add_token_callback):
        """
        This parser is written in a dynamic way, meaning that this parser
        allows using different grammars (even non-Python). However, error
        recovery is purely written for Python.
        """
        # For now just discard everything that is not a suite or
        # file_input, if we detect an error.
        for index, (dfa, state, (_type, nodes)) in reversed(list(enumerate(stack))):
            # `suite` can sometimes be only simple_stmt, not stmt.
            symbol = grammar.number2symbol[_type]
            if symbol in ('file_input', 'suite'):
                break
        #print('err', tokenize.tok_name[typ], repr(value), start_pos, len(stack), index)
        self._stack_removal(grammar, stack, index + 1, value, start_pos)
        if value in ('import', 'from', 'class', 'def', 'try', 'while', 'return'):
            # Those can always be new statements.
            add_token_callback(typ, value, prefix, start_pos)
        elif typ == tokenize.DEDENT:
            if symbol == 'suite':
                if len(nodes) > 2:
                    # Finish the suite.
                    add_token_callback(typ, value, prefix, start_pos)
                else:
                    # If a function or anything else contains a suite that is
                    # "empty" (just NEWLINE/INDENT), we remove it.
                    self._stack_removal(grammar, stack, len(stack) - 2, value, start_pos)

    def _stack_removal(self, grammar, stack, start_index, value, start_pos):
        def clear_names(children):
            for c in children:
                try:
                    clear_names(c.children)
                except AttributeError:
                    if isinstance(c, pt.Name):
                        try:
                            self.scope_names_stack[-1][c.value].remove(c)
                            self.used_names[c.value].remove(c)
                        except ValueError:
                            pass  # This may happen with CompFor.

        for dfa, state, node in stack[start_index:]:
            clear_names(children=node[1])

        failed_stack = []
        found = False
        for dfa, state, (typ, nodes) in stack[start_index:]:
            if nodes:
                found = True
            if found:
                symbol = grammar.number2symbol[typ]
                failed_stack.append((symbol, nodes))
            if nodes and nodes[0] in ('def', 'class'):
                self.scope_names_stack.pop()
        if failed_stack:
            err = ErrorStatement(failed_stack, value, start_pos)
            self.error_statement_stacks.append(err)

        stack[start_index:] = []

    def _tokenize(self, tokenizer):
        """
            while first_pos[1] <= self._scope.start_pos[1] \
                    and (token_type == tokenize.NAME or tok_str in ('(', '['))\
                    and self._scope != self.module:
                self._scope.end_pos = first_pos
                self._scope = self._scope.parent
                if isinstance(self._scope, pr.Module) \
                        and not isinstance(self._scope, pr.SubModule):
                    self._scope = self.module
        """

        new_scope = False
        for token in tokenizer:
            typ = token.type
            value = token.value
            if typ == tokenize.OP:
                typ = pgen2.grammar.opmap[value]
            yield typ, value, token.prefix, token.start_pos


    def __init__old__(self, source, module_path=None, no_docstr=False,
                      tokenizer=None, top_module=None):

        """
        TODO REMOVE THIS
        """
        self.no_docstr = no_docstr

        tokenizer = tokenizer or tokenize.source_tokens(source)
        self._gen = PushBackTokenizer(tokenizer)

        # initialize global Scope
        start_pos = next(self._gen).start_pos
        self._gen.push_last_back()
        self.module = pt.SubModule(module_path, start_pos, top_module)
        self._scope = self.module
        self._top_module = top_module or self.module

        try:
            self._parse()
        except (common.MultiLevelStopIteration, StopIteration):
            # StopIteration needs to be added as well, because python 2 has a
            # strange way of handling StopIterations.
            # sometimes StopIteration isn't catched. Just ignore it.

            # on finish, set end_pos correctly
            pass
        s = self._scope
        while s is not None:
            s.end_pos = self._gen.current.end_pos
            s = s.parent

        # clean up unused decorators
        for d in self._decorators:
            # set a parent for unused decorators, avoid NullPointerException
            # because of `self.module.used_names`.
            d.parent = self.module

        self.module.end_pos = self._gen.current.end_pos
        if self._gen.current.type == tokenize.NEWLINE:
            # This case is only relevant with the FastTokenizer, because
            # otherwise there's always an ENDMARKER.
            # we added a newline before, so we need to "remove" it again.
            #
            # NOTE: It should be keep end_pos as-is if the last token of
            # a source is a NEWLINE, otherwise the newline at the end of
            # a source is not included in a ParserNode.code.
            if self._gen.previous.type != tokenize.NEWLINE:
                self.module.end_pos = self._gen.previous.end_pos

        del self._gen

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.module)

    def _check_user_stmt(self, simple):
        # this is not user checking, just update the used_names
        for tok_name in self.module.temp_used_names:
            try:
                self.module.used_names[tok_name].add(simple)
            except KeyError:
                self.module.used_names[tok_name] = set([simple])
        self.module.temp_used_names = []
        if isinstance(simple, pt.Statement):
            for name, calls in simple.get_names_dict().items():
                self._scope.add_name_calls(name, calls)


class PushBackTokenizer(object):
    def __init__(self, tokenizer):
        self._tokenizer = tokenizer
        self._push_backs = []
        self.current = self.previous = tokenize.Token(None, '', (0, 0))

    def push_last_back(self):
        self._push_backs.append(self.current)

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self._push_backs:
            return self._push_backs.pop(0)

        previous = self.current
        self.current = next(self._tokenizer)
        self.previous = previous
        return self.current

    def __iter__(self):
        return self
