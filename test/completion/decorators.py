# -----------------
# not found decorators
# -----------------
@not_found_decorator
def just_a_func():
    return 1

#? []
just_a_func()

#? []
just_a_func.


class JustAClass:
    @not_found_decorator2
    def a(self):
        return 1

#? []
JustAClass().a.
#? []
JustAClass().a()
#? []
JustAClass.a.
#? []
JustAClass().a()
