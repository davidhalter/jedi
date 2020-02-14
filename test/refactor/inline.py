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
