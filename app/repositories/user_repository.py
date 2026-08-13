from app.database import users_collection
from app.utils.helpers import object_id

class UserRepository:
    def __init__(self):
        self.collection = users_collection

    def find_by_id(self, document_id):
        return self.collection.find_one({"_id": object_id(document_id)})

    def find_by_email(self, email):
        return self.collection.find_one({"email": email.lower()})

    def find_all(self, limit=100):
        return list(self.collection.find({}).limit(limit))

    def insert(self, data):
        return self.collection.insert_one(data)

    def update_by_id(self, document_id, data):
        return self.collection.update_one({"_id": object_id(document_id)}, {"$set": data})
