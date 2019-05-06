from jedi.evaluate.filters import AbstractNameDefinition


class ImportName(AbstractNameDefinition):
    start_pos = (1, 0)
    _level = 0

    def __init__(self, parent_context, string_name):
        self.parent_context = parent_context
        self.string_name = string_name

    def infer(self):
        from jedi.evaluate.imports import Importer
        return Importer(
            self.parent_context.evaluator,
            [self.string_name],
            self.parent_context,
            level=self._level,
        ).follow()

    def goto(self):
        return [m.name for m in self.infer()]

    def get_root_context(self):
        # Not sure if this is correct.
        return self.parent_context.get_root_context()

    @property
    def api_type(self):
        return 'module'


class SubModuleName(ImportName):
    _level = 1
