# -------------------------------------------------- no-name-error
#? 0 error
1
# ++++++++++++++++++++++++++++++++++++++++++++++++++
There is no name under the cursor
# -------------------------------------------------- multi-equal-error
def test():
    #? 4 error
    a = b = 3
    return test(100, a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a statement with multiple definitions
# -------------------------------------------------- no-definition-error
#? 5 error
test(a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
No definition found to inline
# -------------------------------------------------- multi-names-error
#? 0 error
a, b[1] = 3
test(a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a statement with multiple definitions
# -------------------------------------------------- addition-error
#? 0 error
a = 2
a += 3
test(a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a name with multiple definitions
# -------------------------------------------------- only-addition-error
#? 0 error
a += 3
test(a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a statement with "+="
# -------------------------------------------------- with-annotation
foobarb: int = 1
#? 5
test(foobarb)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/inline.py
+++ /home/dave/source/jedi/test/refactor/inline.py
@@ -1,4 +1,4 @@
-foobarb: int = 1
+
 #? 5
-test(foobarb)
+test(1)
# -------------------------------------------------- only-annotation-error
a: int
#? 5 error
test(a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a statement that is defined by an annotation
# -------------------------------------------------- builtin
import math
#? 7 error
math.cos
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline builtins/extensions
# -------------------------------------------------- module
from import_tree import some_mod
#? 11 error
test(some_mod)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline imports or modules
# -------------------------------------------------- class
class A: pass
#? 5 error
test(A)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a class
# -------------------------------------------------- function
def foo(a):
    return a + 1
#? 5 error
test(foo(1))
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a function
# -------------------------------------------------- for-stmt
for x in []:
    #? 9 error
    test(x)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
Cannot inline a for_stmt
# -------------------------------------------------- simple
def test():
    #? 4
    a = (30 + b, c) + 1
    return test(100, a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/inline.py
+++ /home/dave/source/jedi/test/refactor/inline.py
@@ -1,5 +1,4 @@
 def test():
     #? 4
-    a = (30 + b, c) + 1
-    return test(100, a)
+    return test(100, (30 + b, c) + 1)
# -------------------------------------------------- tuple
if 1:
    #? 4
    a = 1, 2
    return test(100, a)
# ++++++++++++++++++++++++++++++++++++++++++++++++++
--- /home/dave/source/jedi/test/refactor/inline.py
+++ /home/dave/source/jedi/test/refactor/inline.py
@@ -1,5 +1,4 @@
 if 1:
     #? 4
-    a = 1, 2
-    return test(100, a)
+    return test(100, (1, 2))
