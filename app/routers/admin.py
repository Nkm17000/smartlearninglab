from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.mongo import get_db
from app.core.security import require_admin
from app.services.query import paginated
from app.utils import oid, serialize_doc

router = APIRouter(prefix="/admin", tags=["Admin"])


class ContentPayload(BaseModel):
    name: str | None = None
    title: str | None = None
    description: str | None = None
    code: str | None = None
    active: bool = True
    order: int = 0
    examIds: list[str] = Field(default_factory=list)
    subjectIds: list[str] = Field(default_factory=list)
    topicId: str | None = None


@router.get("/dashboard")
def dashboard(admin=Depends(require_admin)):
    db = get_db()
    return {
        "users": db.users.count_documents({}),
        "exams": db.exams.count_documents({}),
        "courses": db.courses.count_documents({}),
        "lessons": db.lessons.count_documents({}),
        "questions": db.questions.count_documents({}),
        "mockTests": db.mock_tests.count_documents({}),
        "currentAffairs": db.current_affairs.count_documents({}),
    }


def create_generic(collection_name: str, payload: ContentPayload):
    db = get_db()
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    now = datetime.now(timezone.utc)
    data.update({"createdAt": now, "updatedAt": now})
    result = db[collection_name].insert_one(data)
    data["_id"] = result.inserted_id
    return serialize_doc(data)


@router.post("/exams")
def create_exam(payload: ContentPayload, admin=Depends(require_admin)):
    return create_generic("exams", payload)


@router.post("/subjects")
def create_subject(payload: ContentPayload, admin=Depends(require_admin)):
    return create_generic("subjects", payload)


@router.post("/topics")
def create_topic(payload: ContentPayload, admin=Depends(require_admin)):
    return create_generic("topics", payload)


@router.post("/courses")
def create_course(payload: ContentPayload, admin=Depends(require_admin)):
    return create_generic("courses", payload)


@router.post("/lessons")
def create_lesson(payload: ContentPayload, admin=Depends(require_admin)):
    return create_generic("lessons", payload)


class QuestionPayload(BaseModel):
    examIds: list[str] = Field(default_factory=list)
    subjectId: str
    topicId: str
    question: str
    options: list[str] = Field(default_factory=list)
    correctAnswer: str
    explanation: str | None = None
    shortcut: str | None = None
    difficulty: str = "medium"
    type: str = "mcq"
    marks: float = 1
    negativeMarks: float = 0
    language: str = "en"
    status: str = "published"


@router.post("/questions")
def create_question(payload: QuestionPayload, admin=Depends(require_admin)):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"createdAt": now, "updatedAt": now})
    result = db.questions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/questions")
def admin_questions(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin=Depends(require_admin),
):
    query = {}
    if status:
        query["status"] = status
    return paginated(get_db().questions, query, page, limit, [("createdAt", -1)])


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, admin=Depends(require_admin)):
    db = get_db()
    try:
        result = db.questions.update_one(
            {"_id": oid(question_id)},
            {"$set": {"status": "deleted", "updatedAt": datetime.now(timezone.utc)}}
        )
    except ValueError:
        raise HTTPException(400, "Invalid question id")
    if result.matched_count == 0:
        raise HTTPException(404, "Question not found")
    return {"message": "Question retired"}
