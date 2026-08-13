from fastapi import APIRouter
from app.database import lessons_collection
from app.utils.helpers import serialize_document, object_id

router = APIRouter()

@router.get("")
def get_lessons(course_id: str | None = None):
    query = {}
    if course_id:
        query["course_id"] = object_id(course_id)
    return {"status": "success", "data": [serialize_document(x) for x in lessons_collection.find(query).sort("display_order", 1)]}

@router.get("/{lesson_id}")
def get_lesson(lesson_id: str):
    return {"status": "success", "data": serialize_document(lessons_collection.find_one({"_id": object_id(lesson_id)}))}
