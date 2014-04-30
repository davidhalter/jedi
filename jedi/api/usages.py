from jedi._compatibility import u, unicode
from jedi import common
from jedi.api import classes
from jedi.parser import representation as pr
from jedi.evaluate import imports
from jedi.evaluate import helpers


def usages(evaluator, definitions, search_name, mods):
    def compare_array(definitions):
        """ `definitions` are being compared by module/start_pos, because
        sometimes the id's of the objects change (e.g. executions).
        """
        result = []
        for d in definitions:
            module = d.get_parent_until()
            result.append((module, d.start_pos))
        return result

    def check_call_for_usage(call):
        stmt = call.parent
        while not isinstance(stmt.parent, pr.IsScope):
            stmt = stmt.parent
        # New definition, call cannot be a part of stmt
        if len(call.name) == 1 and call.execution is None \
                and call.name in stmt.get_defined_names():
            # Class params are not definitions (like function params). They
            # are super classes, that need to be resolved.
            if not (isinstance(stmt, pr.Param) and isinstance(stmt.parent, pr.Class)):
                return

        follow = []  # There might be multiple search_name's in one call_path
        call_path = list(call.generate_call_path())
        for i, name in enumerate(call_path):
            # name is `pr.NamePart`.
            if u(name) == search_name:
                follow.append(call_path[:i + 1])

        for call_path in follow:
            follow_res, search = evaluator.goto(call.parent, call_path)
            # names can change (getattr stuff), therefore filter names that
            # don't match `search`.

            # TODO add something like that in the future - for now usages are
            # completely broken anyway.
            #follow_res = [r for r in follow_res if str(r) == search]
            #print search.start_pos,search_name.start_pos
            #print follow_res, search, search_name, [(r, r.start_pos) for r in follow_res]
            follow_res = usages_add_import_modules(evaluator, follow_res, search)

            compare_follow_res = compare_array(follow_res)
            # compare to see if they match
            if any(r in compare_definitions for r in compare_follow_res):
                yield classes.Definition(evaluator, search)

    if not definitions:
        return set()

    compare_definitions = compare_array(definitions)
    mods |= set([d.get_parent_until() for d in definitions])
    names = []
    for m in imports.get_modules_containing_name(mods, search_name):
        try:
            stmts = m.used_names[search_name]
        except KeyError:
            continue
        for stmt in stmts:
            if isinstance(stmt, pr.Import):
                count = 0
                imps = []
                for i in stmt.get_all_import_names():
                    for name_part in i.names:
                        count += 1
                        if unicode(name_part) == search_name:
                            imps.append((count, name_part))

                for used_count, name_part in imps:
                    i = imports.ImportWrapper(evaluator, stmt, kill_count=count - used_count,
                                              direct_resolve=True)
                    f = i.follow(is_goto=True)
                    if set(f) & set(definitions):
                        names.append(classes.Definition(evaluator, name_part))
            else:
                for call in helpers.scan_statement_for_calls(stmt, search_name, assignment_details=True):
                    names += check_call_for_usage(call)
    return names


def usages_add_import_modules(evaluator, definitions, search_name):
    """ Adds the modules of the imports """
    new = set()
    for d in definitions:
        if isinstance(d.parent, pr.Import):
            s = imports.ImportWrapper(evaluator, d.parent, direct_resolve=True)
            with common.ignored(IndexError):
                new.add(s.follow(is_goto=True)[0])
    return set(definitions) | new
