from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import get_db
from app.core.deps import current_user, require_admin
from app.schemas.common import EntityCreate, QuestionCreate
import uuid
from datetime import datetime

router = APIRouter(tags=["Learning"])

COLLECTIONS = [
    "exams",
    "subjects",
    "topics",
    "courses",
    "lessons",
    "mock_tests",
    "current_affairs",
]


def clean(d):
    if not d:
        return None
    d["id"] = str(d.pop("_id"))
    return d


@router.get("/exams")
def exams():
    return [
        clean(x) for x in get_db().exams.find({"is_published": True}).sort("order", 1)
    ]


@router.get("/exams/{item_id}")
def exam(item_id: str):
    x = get_db().exams.find_one({"_id": item_id})
    if not x:
        raise HTTPException(404, "Exam not found")
    return clean(x)


@router.get("/subjects")
def subjects(exam_id: str | None = None):
    q = {"is_published": True}
    if exam_id:
        q["exam_id"] = exam_id
    return [clean(x) for x in get_db().subjects.find(q).sort("order", 1)]


@router.get("/topics")
def topics(subject_id: str | None = None):
    q = {"is_published": True}
    if subject_id:
        q["subject_id"] = subject_id
    return [clean(x) for x in get_db().topics.find(q).sort("order", 1)]


@router.get("/courses")
def courses(subject_id: str | None = None, topic_id: str | None = None):
    q = {"is_published": True}
    if subject_id:
        q["subject_id"] = subject_id
    if topic_id:
        q["topic_id"] = topic_id
    return [clean(x) for x in get_db().courses.find(q).sort("order", 1)]


@router.get("/lessons")
def lessons(course_id: str | None = None):
    q = {"is_published": True}
    if course_id:
        q["course_id"] = course_id
    return [clean(x) for x in get_db().lessons.find(q).sort("order", 1)]


@router.get("/questions")
def questions(
    topic_id: str | None = None, subject_id: str | None = None, limit: int = 20
):
    q = {"is_published": True}
    if topic_id:
        q["topic_id"] = topic_id
    if subject_id:
        q["subject_id"] = subject_id
    return [clean(x) for x in get_db().questions.find(q).limit(min(limit, 100))]


@router.get("/mock-tests")
def mock_tests():
    return [clean(x) for x in get_db().mock_tests.find({"is_published": True})]


@router.get("/current-affairs")
def current_affairs():
    return [
        clean(x)
        for x in get_db()
        .current_affairs.find({"is_published": True})
        .sort("date", -1)
        .limit(50)
    ]


@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    db = get_db()
    uid = str(user["_id"])
    return {
        "user": {
            "id": uid,
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
        "overallProgress": db.progress.count_documents({"user_id": uid}),
        "today": {"lessons": 0, "questions": 0, "revision": 0},
        "continueLearning": clean(db.courses.find_one({"is_published": True})),
        "recentTests": [],
        "weakSubjects": [],
        "streak": 0,
    }


@router.post("/progress")
def save_progress(payload: dict, user=Depends(current_user)):
    payload = dict(payload)
    payload["user_id"] = str(user["_id"])
    payload["updated_at"] = datetime.utcnow()
    get_db().progress.update_one(
        {"user_id": payload["user_id"], "item_id": payload.get("item_id")},
        {"$set": payload},
        upsert=True,
    )
    return {"success": True}


@router.post("/tests/{test_id}/submit")
def submit_test(test_id: str, payload: dict, user=Depends(current_user)):
    db = get_db()
    test = db.mock_tests.find_one({"_id": test_id})
    if not test:
        raise HTTPException(404, "Test not found")
    answers = payload.get("answers", {})
    correct = 0
    for q in test.get("questions", []):
        qid = str(q.get("id") or q.get("_id"))
        if answers.get(qid) == q.get("answer"):
            correct += 1
    total = len(test.get("questions", []))
    result = {
        "_id": uuid.uuid4().hex,
        "user_id": str(user["_id"]),
        "test_id": test_id,
        "score": correct,
        "total": total,
        "answers": answers,
        "created_at": datetime.utcnow(),
    }
    db.test_results.insert_one(result)
    return {
        "score": correct,
        "total": total,
        "percentage": round((correct / total) * 100, 2) if total else 0,
    }
