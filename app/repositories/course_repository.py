from app.repositories.base import Repository
class CourseRepository(Repository):
    def __init__(self):
        super().__init__("courses")
