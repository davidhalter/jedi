try:
    #! 4 attribute-error
    str.not_existing
except TypeError:
    pass

try:
    str.not_existing
except AttributeError:
    #! 4 attribute-error
    str.not_existing
    pass

try:
    import not_existing_import
except ImportError:
    pass
try:
    #! 7 import-error
    import not_existing_import
except AttributeError:
    pass

# -----------------
# multi except
# -----------------
try:
    str.not_existing
except (TypeError, AttributeError): pass

try:
    str.not_existing
except ImportError:
    pass
except (NotImplementedError, AttributeError): pass

try:
    #! 4 attribute-error
    str.not_existing
except (TypeError, NotImplementedError): pass

# -----------------
# detailed except
# -----------------
try:
    str.not_existing
except ((AttributeError)): pass
try:
    #! 4 attribute-error
    str.not_existing
except [AttributeError]: pass
