from app.repositories.base import Repository
class QuizRepository(Repository):
    def __init__(self):
        super().__init__("quizs")
