from app.database import courses_collection

class CourseRepository:
    def __init__(self):
        self.collection = courses_collection

    def find_by_id(self, document_id):
        from app.utils.helpers import object_id
        return self.collection.find_one({"_id": object_id(document_id)})

    def find_all(self, filter_query=None, limit=100):
        return list(self.collection.find(filter_query or {}).limit(limit))

    def insert(self, data):
        return self.collection.insert_one(data)

    def update_by_id(self, document_id, data):
        from app.utils.helpers import object_id
        return self.collection.update_one(
            {"_id": object_id(document_id)},
            {"$set": data}
        )

    def delete_by_id(self, document_id):
        from app.utils.helpers import object_id
        return self.collection.delete_one({"_id": object_id(document_id)})
