from app.repositories.base import Repository
class QuestionRepository(Repository):
    def __init__(self):
        super().__init__("questions")
