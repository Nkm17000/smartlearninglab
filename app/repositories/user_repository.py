from app.repositories.base import Repository
class UserRepository(Repository):
    def __init__(self):
        super().__init__("users")
