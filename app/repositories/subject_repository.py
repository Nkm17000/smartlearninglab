from app.repositories.base import Repository
class SubjectRepository(Repository):
    def __init__(self):
        super().__init__("subjects")
