class partial():
    def __init__(self, func, *args, **keywords):
        self.__func = func
        self.__args = args
        self.__keywords = keywords

    def __call__(self, *args, **kwargs):
        # I know this doesn't work in Python, but Jedi can this ;-)
        return self.__func(*self.__args, *args, **self.keywords, **kwargs)
