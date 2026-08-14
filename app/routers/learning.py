from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.services.query import paginated
from app.utils import serialize_doc, oid

router = APIRouter(prefix="/learning", tags=["Learning"])


@router.get("/categories")
def categories():
    return [serialize_doc(x) for x in get_db().exam_categories.find({"active": {"$ne": False}}).sort("name", 1)]


@router.get("/subjects")
def subjects(exam_id: str | None = None):
    query = {"active": {"$ne": False}}
    if exam_id:
        query["examIds"] = exam_id
    return [serialize_doc(x) for x in get_db().subjects.find(query).sort("order", 1)]


@router.get("/subjects/{subject_id}/topics")
def topics(subject_id: str):
    return [serialize_doc(x) for x in get_db().topics.find({"subjectId": subject_id}).sort("order", 1)]


@router.get("/topics/{topic_id}")
def topic(topic_id: str):
    db = get_db()
    doc = db.topics.find_one({"_id": oid(topic_id)}) if len(topic_id) == 24 else db.topics.find_one({"code": topic_id})
    if not doc:
        raise HTTPException(404, "Topic not found")
    return serialize_doc(doc)


@router.get("/courses")
def courses(
    exam_id: str | None = None,
    subject_id: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = {"active": {"$ne": False}}
    if exam_id:
        query["examIds"] = exam_id
    if subject_id:
        query["subjectIds"] = subject_id
    if search:
        query["title"] = {"$regex": search, "$options": "i"}
    return paginated(get_db().courses, query, page, limit, [("createdAt", -1)])


@router.get("/courses/{course_id}")
def course(course_id: str):
    db = get_db()
    doc = db.courses.find_one({"_id": oid(course_id)}) if len(course_id) == 24 else db.courses.find_one({"code": course_id})
    if not doc:
        raise HTTPException(404, "Course not found")
    sections = list(db.course_sections.find({"courseId": str(doc["_id"])}).sort("order", 1))
    lessons = list(db.lessons.find({"courseId": str(doc["_id"])}).sort("order", 1))
    result = serialize_doc(doc)
    result["sections"] = [serialize_doc(x) for x in sections]
    result["lessons"] = [serialize_doc(x) for x in lessons]
    return result


@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: str):
    db = get_db()
    doc = db.lessons.find_one({"_id": oid(lesson_id)}) if len(lesson_id) == 24 else db.lessons.find_one({"code": lesson_id})
    if not doc:
        raise HTTPException(404, "Lesson not found")
    resources = list(db.lesson_resources.find({"lessonId": str(doc["_id"])}))
    result = serialize_doc(doc)
    result["resources"] = [serialize_doc(x) for x in resources]
    return result


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str, current_user=Depends(get_current_user)):
    db = get_db()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.student_progress.update_one(
        {"userId": current_user["id"], "lessonId": lesson_id},
        {"$set": {"completed": True, "completedAt": now, "updatedAt": now},
         "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return {"message": "Lesson marked complete", "lessonId": lesson_id}
