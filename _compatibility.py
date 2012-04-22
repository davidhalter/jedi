
# python2.5 compatibility
try:
    next = next
except NameError:
    def next(obj):
        return obj.next()
