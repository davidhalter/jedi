
class Super(object):
    attribute = 3

    def func(self):
        return 1

    class Inner():
        pass


class Sub(Super):
    #? 13 Sub.attribute
    def attribute(self):
        pass

    #! 8 ['attribute = 3']
    def attribute(self):
        pass

    #! 4 ['def func']
    func = 3
    #! 12 ['def func']
    class func(): ...

    #! 8 ['class Inner']
    def Inner(self): ...
