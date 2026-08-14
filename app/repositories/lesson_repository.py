from app.repositories.base import Repository
class LessonRepository(Repository):
    def __init__(self):
        super().__init__("lessons")
