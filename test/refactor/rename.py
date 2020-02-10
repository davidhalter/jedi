"""
Test coverage for renaming is mostly being done by testing
`Script.get_references`.
"""

# ----- simple
def test1():
    #? 7 blabla
    test1()
    AssertionError
    return test1, test1.not_existing
# +++++
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,6 +1,6 @@
-def test1():
+def blabla():
     #? 7 blabla
-    test1()
+    blabla()
     AssertionError
-    return test1, test1.not_existing
+    return blabla, blabla.not_existing
# ----- different-scopes
def x():
    #? 7 v
    some_var = 3
    some_var
def y():
    some_var = 3
    some_var
# +++++
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,7 +1,7 @@
 def x():
     #? 7 v
-    some_var = 3
-    some_var
+    v = 3
+    v
 def y():
     some_var = 3
     some_var
# ----- import
from import_tree.mod1 import foobarbaz
#? 0 renamed
foobarbaz
# +++++
--- /home/dave/source/jedi/test/completion/import_tree/mod1.py
+++ /home/dave/source/jedi/test/completion/import_tree/mod1.py
@@ -1,5 +1,5 @@
 a = 1
 from import_tree.random import a as c
 
-foobarbaz = 3.0
+renamed = 3.0
--- /home/dave/source/jedi/test/refactor/rename.py
+++ /home/dave/source/jedi/test/refactor/rename.py
@@ -1,4 +1,4 @@
-from import_tree.mod1 import foobarbaz
+from import_tree.mod1 import renamed
 #? 0 renamed
-foobarbaz
+renamed
