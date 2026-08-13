from app.repositories.user_repository import UserRepository
from app.utils.helpers import serialize_document

class UserService:
    def __init__(self):
        self.repository = UserRepository()

    def get_by_id(self, user_id):
        return serialize_document(self.repository.find_by_id(user_id))

    def get_all(self):
        return [serialize_document(x) for x in self.repository.find_all()]
