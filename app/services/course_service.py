from app.repositories.course_repository import CourseRepository
from app.utils.helpers import serialize_document

class CourseService:
    def __init__(self):
        self.repository = CourseRepository()

    def get_all(self, filter_query=None):
        return [serialize_document(x) for x in self.repository.find_all(filter_query)]

    def get_by_id(self, document_id):
        return serialize_document(self.repository.find_by_id(document_id))

    def create(self, data):
        result = self.repository.insert(data)
        return serialize_document(self.repository.find_by_id(str(result.inserted_id)))
