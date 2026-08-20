from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import admin_user
from app.db.mongo import get_db

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

ALLOWED = {
    "exams",
    "subjects",
    "topics",
    "courses",
    "lessons",
    "questions",
    "mock_tests",
    "quizzes",
    "current_affairs",
}


def clean(value):
    """Make Mongo/Python values safe for JSON responses."""
    try:
        from bson import ObjectId
    except Exception:
        ObjectId = ()

    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if ObjectId and isinstance(value, ObjectId):
        return str(value)
    return value


def ensure(data: dict, kind: str) -> dict:
    d = dict(data)
    d.setdefault("_id", uuid.uuid4().hex)
    now = datetime.now(timezone.utc)
    d.setdefault("created_at", now)
    d.setdefault("updated_at", now)
    if kind in {"courses", "lessons", "questions", "mock_tests", "quizzes"}:
        d.setdefault("is_published", False)
    return d


def find_by_id(collection: str, item_id: str):
    """The project uses string UUIDs, but also tolerates ObjectId data."""
    db = get_db()
    item = db[collection].find_one({"_id": item_id})
    if item:
        return item

    try:
        from bson import ObjectId
        if ObjectId.is_valid(item_id):
            return db[collection].find_one({"_id": ObjectId(item_id)})
    except Exception:
        pass

    return None


@router.get("/dashboard")
def dashboard(user=Depends(admin_user)):
    db = get_db()
    counts = {
        c: db[c].count_documents({})
        for c in ["users", "courses", "lessons", "questions", "quizzes", "mock_tests"]
    }
    published = {
        c: db[c].count_documents({"is_published": True})
        for c in ["courses", "lessons", "questions", "quizzes", "mock_tests"]
    }

    # Return both the structured counts and simple values so older/newer FEs work.
    return {
        "admin": {"id": str(user["_id"]), "name": user.get("name", "Admin")},
        "counts": counts,
        "published": published,
        "courses": counts["courses"],
        "lessons": counts["lessons"],
        "questions": counts["questions"],
        "quizzes": counts["quizzes"],
        "students": db.users.count_documents({"role": "student"}),
    }


# ---------------------------------------------------------------------------
# Professional course APIs used by the Admin FE
# ---------------------------------------------------------------------------

@router.get("/courses")
def list_courses(
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(admin_user),
):
    q = {}
    if search:
        q = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]
        }
    return [clean(x) for x in get_db().courses.find(q).sort("created_at", -1).limit(limit)]


@router.post("/courses")
def create_course(data: dict, user=Depends(admin_user)):
    d = ensure(data, "courses")
    if not d.get("name") and d.get("title"):
        d["name"] = d["title"]
    if not d.get("name"):
        raise HTTPException(422, "Course name is required")
    get_db().courses.insert_one(d)
    return clean(d)


@router.get("/courses/{course_id}")
def get_course(course_id: str, user=Depends(admin_user)):
    course = find_by_id("courses", course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return clean(course)


@router.put("/courses/{course_id}")
def update_course(course_id: str, data: dict, user=Depends(admin_user)):
    return _update("courses", course_id, data)


@router.delete("/courses/{course_id}")
def delete_course(course_id: str, user=Depends(admin_user)):
    return _delete("courses", course_id)


@router.post("/courses/{course_id}/modules")
def create_module(course_id: str, data: dict, user=Depends(admin_user)):
    if not find_by_id("courses", course_id):
        raise HTTPException(404, "Course not found")
    data = dict(data)
    data["course_id"] = course_id
    data.setdefault("name", data.get("title", ""))
    return _create("topics", data)


@router.get("/courses/{course_id}/modules")
def list_modules(course_id: str, user=Depends(admin_user)):
    if not find_by_id("courses", course_id):
        raise HTTPException(404, "Course not found")
    return [
        clean(x)
        for x in get_db().topics.find({"course_id": course_id}).sort("order", 1)
    ]


@router.put("/modules/{module_id}")
def update_module(module_id: str, data: dict, user=Depends(admin_user)):
    return _update("topics", module_id, data)


@router.delete("/modules/{module_id}")
def delete_module(module_id: str, user=Depends(admin_user)):
    return _delete("topics", module_id)


@router.post("/modules/{module_id}/lessons")
def create_lesson(module_id: str, data: dict, user=Depends(admin_user)):
    module = find_by_id("topics", module_id)
    if not module:
        raise HTTPException(404, "Module not found")

    data = dict(data)
    data["topic_id"] = module_id
    if module.get("course_id"):
        data.setdefault("course_id", module["course_id"])
    data.setdefault("name", data.get("title", ""))
    data.setdefault("title", data.get("name", ""))
    return _create("lessons", data)


@router.get("/modules/{module_id}/lessons")
def list_lessons(module_id: str, user=Depends(admin_user)):
    if not find_by_id("topics", module_id):
        raise HTTPException(404, "Module not found")
    return [
        clean(x)
        for x in get_db().lessons.find({"topic_id": module_id}).sort("order", 1)
    ]


@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: str, data: dict, user=Depends(admin_user)):
    return _update("lessons", lesson_id, data)


@router.delete("/lessons/{lesson_id}")
def delete_lesson(lesson_id: str, user=Depends(admin_user)):
    return _delete("lessons", lesson_id)


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

@router.get("/questions")
def list_questions(
    search: str | None = None,
    difficulty: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    user=Depends(admin_user),
):
    q = {}
    conditions = []
    if search:
        conditions.append({"question": {"$regex": search, "$options": "i"}})
    if difficulty:
        conditions.append({"difficulty": difficulty.lower()})
    if conditions:
        q = conditions[0] if len(conditions) == 1 else {"$and": conditions}
    return [clean(x) for x in get_db().questions.find(q).sort("created_at", -1).limit(limit)]


@router.post("/questions")
def create_question(data: dict, user=Depends(admin_user)):
    d = ensure(data, "questions")
    d.setdefault("question_type", "mcq")
    d.setdefault("difficulty", "easy")
    d.setdefault("marks", 1)
    d.setdefault("negative_marks", 0)
    d.setdefault("options", [])
    d.setdefault("explanation", "")
    get_db().questions.insert_one(d)
    return clean(d)


@router.get("/questions/{question_id}")
def get_question(question_id: str, user=Depends(admin_user)):
    item = find_by_id("questions", question_id)
    if not item:
        raise HTTPException(404, "Question not found")
    return clean(item)


@router.put("/questions/{question_id}")
def update_question(question_id: str, data: dict, user=Depends(admin_user)):
    return _update("questions", question_id, data)


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, user=Depends(admin_user)):
    return _delete("questions", question_id)


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------

@router.get("/quizzes")
def list_quizzes(
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(admin_user),
):
    q = {}
    if search:
        q = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"title": {"$regex": search, "$options": "i"}},
            ]
        }
    return [clean(x) for x in get_db().quizzes.find(q).sort("created_at", -1).limit(limit)]


@router.post("/quizzes")
def create_quiz(data: dict, user=Depends(admin_user)):
    d = ensure(data, "quizzes")
    if not d.get("title") and d.get("name"):
        d["title"] = d["name"]
    if not d.get("title"):
        raise HTTPException(422, "Quiz title is required")
    d.setdefault("duration_minutes", 15)
    d.setdefault("passing_percentage", 60)
    d.setdefault("max_attempts", 3)
    d.setdefault("randomize_questions", True)
    d.setdefault("randomize_options", True)
    d.setdefault("question_ids", [])
    get_db().quizzes.insert_one(d)
    return clean(d)


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: str, user=Depends(admin_user)):
    item = find_by_id("quizzes", quiz_id)
    if not item:
        raise HTTPException(404, "Quiz not found")
    return clean(item)


@router.put("/quizzes/{quiz_id}")
def update_quiz(quiz_id: str, data: dict, user=Depends(admin_user)):
    return _update("quizzes", quiz_id, data)


@router.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: str, user=Depends(admin_user)):
    return _delete("quizzes", quiz_id)


@router.post("/quizzes/{quiz_id}/questions")
def add_quiz_questions(quiz_id: str, data: dict, user=Depends(admin_user)):
    quiz = find_by_id("quizzes", quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")

    question_ids = data.get("question_ids")
    if question_ids is None:
        one = data.get("question_id")
        question_ids = [one] if one else []
    if not isinstance(question_ids, list) or not question_ids:
        raise HTTPException(400, "question_ids must contain at least one question id")

    existing = quiz.get("question_ids", []) or []
    for qid in question_ids:
        if not find_by_id("questions", str(qid)):
            raise HTTPException(404, f"Question not found: {qid}")
        if qid not in existing:
            existing.append(qid)

    now = datetime.now(timezone.utc)
    get_db().quizzes.update_one(
        {"_id": quiz["_id"]},
        {"$set": {"question_ids": existing, "updated_at": now}},
    )
    return {"quiz_id": str(quiz["_id"]), "question_ids": existing}


@router.delete("/quizzes/{quiz_id}/questions/{question_id}")
def remove_quiz_question(quiz_id: str, question_id: str, user=Depends(admin_user)):
    quiz = find_by_id("quizzes", quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    get_db().quizzes.update_one(
        {"_id": quiz["_id"]},
        {
            "$pull": {"question_ids": question_id},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return {"message": "Question removed"}


# ---------------------------------------------------------------------------
# Backward-compatible generic admin CRUD
# ---------------------------------------------------------------------------

@router.get("/{collection}")
def list_items(
    collection: str,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(admin_user),
):
    if collection not in ALLOWED:
        raise HTTPException(400, "Unsupported collection")
    q = {}
    if search:
        q = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"title": {"$regex": search, "$options": "i"}},
                {"question": {"$regex": search, "$options": "i"}},
            ]
        }
    return [clean(x) for x in get_db()[collection].find(q).sort("created_at", -1).limit(limit)]


@router.post("/{collection}")
def create_item(collection: str, data: dict, user=Depends(admin_user)):
    if collection not in ALLOWED:
        raise HTTPException(400, "Unsupported collection")
    return _create(collection, data)


@router.put("/{collection}/{item_id}")
def update_item(collection: str, item_id: str, data: dict, user=Depends(admin_user)):
    if collection not in ALLOWED:
        raise HTTPException(400, "Unsupported collection")
    return _update(collection, item_id, data)


@router.delete("/{collection}/{item_id}")
def delete_item(collection: str, item_id: str, user=Depends(admin_user)):
    if collection not in ALLOWED:
        raise HTTPException(400, "Unsupported collection")
    return _delete(collection, item_id)


# Internal helpers keep all update/delete behavior consistent.
def _create(collection: str, data: dict):
    d = ensure(data, collection)
    get_db()[collection].insert_one(d)
    return clean(d)


def _update(collection: str, item_id: str, data: dict):
    existing = find_by_id(collection, item_id)
    if not existing:
        raise HTTPException(404, "Item not found")

    data = dict(data)
    data.pop("_id", None)
    data["updated_at"] = datetime.now(timezone.utc)
    get_db()[collection].update_one({"_id": existing["_id"]}, {"$set": data})
    return clean(get_db()[collection].find_one({"_id": existing["_id"]}))


def _delete(collection: str, item_id: str):
    existing = find_by_id(collection, item_id)
    if not existing:
        raise HTTPException(404, "Item not found")
    get_db()[collection].delete_one({"_id": existing["_id"]})
    return {"message": "Deleted"}
