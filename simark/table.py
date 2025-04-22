from parse import rollback_no_match, Context, Entity, Group, Phrase, Annotation

class Cell(Group):

    def __init__(self, children: list[Entity], annotations: list[Annotation]):
        super().__init__(children)
        self.annotations = annotations

    def walk(self, func, level=0, skip=False):
        super().walk(func, level=level, skip=skip)
        if self.annotations:
            for annotation in self.annotations:
                annotation.walk(func, level=level+1)

    annotation_names = {"rowspan", "colspan"}

    @staticmethod
    @rollback_no_match
    def read(context: Context):
        phrase = Phrase.read(context)
        if phrase is None:
            return None
        annotations = []
        for child in phrase.children:
            if isinstance(child, Annotation) and child.name in Cell.annotation_names:
                annotations.append(child)
        return Cell(phrase.children, annotations)

