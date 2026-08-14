from app.database import collection
from app.utils import oid, clean_doc

class Repository:
    def __init__(self, name):
        self.col = collection(name)

    def all(self, query=None, limit=200):
        return [clean_doc(x) for x in self.col.find(query or {}).limit(limit)]

    def by_id(self, value):
        return clean_doc(self.col.find_one({"_id": oid(value)}))
