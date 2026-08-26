from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import admin_user, root_admin_user, hash_password
from app.db.mongo import get_db
from app.services.taxonomy import all_taxonomy

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

def now():
    return datetime.now(timezone.utc)

def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v, ObjectId):
            return str(v)
    except Exception:
        pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v

def find_by_id(collection, item_id):
    db = get_db()
    x = db[collection].find_one({"_id": item_id})
    if x:
        return x
    try:
        from bson import ObjectId
        if ObjectId.is_valid(item_id):
            return db[collection].find_one({"_id": ObjectId(item_id)})
    except Exception:
        pass
    return None

def make_doc(data, published=False):
    d = dict(data or {})
    d.setdefault("_id", uuid.uuid4().hex)
    d.setdefault("created_at", now())
    d["updated_at"] = now()
    if published:
        d.setdefault("is_published", False)
    return d

def create_doc(collection, data, published=False):
    d = make_doc(data, published)
    get_db()[collection].insert_one(d)
    return clean(d)

def update_doc(collection, item_id, data):
    old = find_by_id(collection, item_id)
    if not old:
        raise HTTPException(404, f"{collection} item not found")
    d = dict(data or {})
    d.pop("_id", None)
    d["updated_at"] = now()
    get_db()[collection].update_one({"_id": old["_id"]}, {"$set": d})
    return clean(get_db()[collection].find_one({"_id": old["_id"]}))

def delete_doc(collection, item_id):
    old = find_by_id(collection, item_id)
    if not old:
        raise HTTPException(404, "Item not found")
    get_db()[collection].delete_one({"_id": old["_id"]})
    return {"message": "Deleted", "id": str(old["_id"])}

# Dashboard
@router.get("/taxonomy")
def admin_taxonomy(user=Depends(admin_user)):
    """Return the full category/subcategory taxonomy used by admin content forms.

    The endpoint is intentionally backed by the same taxonomy service used by
    bulk uploads, courses, quizzes, and the admin taxonomy screen.
    """
    return {"categories": all_taxonomy()}

@router.get("/dashboard")
def dashboard(user=Depends(admin_user)):
    db = get_db()
    courses = db.courses.count_documents({})
    published_courses = db.courses.count_documents({"is_published": True})
    modules = db.topics.count_documents({})
    lessons = db.lessons.count_documents({})
    questions = db.questions.count_documents({})
    quizzes = db.quizzes.count_documents({})
    published_quizzes = db.quizzes.count_documents({"is_published": True})
    students = db.users.count_documents({"role": "student"})
    admins = db.users.count_documents({"role": {"$in": ["root_admin", "admin", "content_admin", "instructor", "support_admin"]}})
    quiz_attempts = sum(db[name].count_documents({}) for name in ("quiz_attempts", "quiz_results", "results"))
    counts = {"courses": courses, "published_courses": published_courses, "draft_courses": courses-published_courses, "modules": modules, "lessons": lessons, "questions": questions, "quizzes": quizzes, "published_quizzes": published_quizzes, "students": students, "admins": admins, "quiz_attempts": quiz_attempts}
    return {"admin": {"id": str(user["_id"]), "name": user.get("name", "Admin"), "role": user.get("role")}, "counts": counts, **counts}

# Courses
@router.get("/courses")
def courses(search: str | None = None, user=Depends(admin_user)):
    q = {}
    if search:
        q = {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]}
    return [clean(x) for x in get_db().courses.find(q).sort("created_at", -1)]

@router.post("/courses")
def create_course(data: dict, user=Depends(admin_user)):
    d = dict(data)
    d.setdefault("name", d.get("title", ""))
    if not d.get("name"):
        raise HTTPException(422, "Course name is required")
    d.setdefault("title", d["name"])
    d.setdefault("description", "")
    d.setdefault("short_description", "")
    d.setdefault("level", "Beginner")
    d.setdefault("category", "General")
    d.setdefault("language", "English")
    d.setdefault("learning_objectives", [])
    d.setdefault("prerequisites", [])
    d.setdefault("estimated_minutes", 0)
    d.setdefault("thumbnail_url", "")
    d.setdefault("banner_url", "")
    d.setdefault("instructor_name", "Smart Learning Lab")
    d.setdefault("exam", "General")
    d.setdefault("tags", [])
    d.setdefault("featured", False)
    d.setdefault("is_free", True)
    d.setdefault("rating", 0)
    d.setdefault("students_count", 0)
    d.setdefault("video_count", 0)
    d.setdefault("pdf_count", 0)
    d.setdefault("mock_test_count", 0)
    d.setdefault("is_published", False)
    return create_doc("courses", d, True)

@router.get("/courses/{course_id}")
def course(course_id: str, user=Depends(admin_user)):
    x = find_by_id("courses", course_id)
    if not x: raise HTTPException(404, "Course not found")
    return clean(x)

@router.put("/courses/{course_id}")
def update_course(course_id: str, data: dict, user=Depends(admin_user)):
    return update_doc("courses", course_id, data)

@router.delete("/courses/{course_id}")
def delete_course(course_id: str, user=Depends(admin_user)):
    db = get_db()
    if not find_by_id("courses", course_id):
        raise HTTPException(404, "Course not found")
    db.courses.delete_one({"_id": find_by_id("courses", course_id)["_id"]})
    db.topics.delete_many({"course_id": course_id})
    db.lessons.delete_many({"course_id": course_id})
    return {"message": "Course and its modules/lessons deleted"}

@router.post("/courses/{course_id}/publish")
def publish_course(course_id: str, user=Depends(admin_user)):
    course = find_by_id("courses", course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    db = get_db()
    lesson_count = db.lessons.count_documents({"course_id": course_id})
    if lesson_count == 0:
        raise HTTPException(400, "Add at least one lesson before publishing the course")
    return update_doc("courses", course_id, {"is_published": True})

@router.post("/courses/{course_id}/unpublish")
def unpublish_course(course_id: str, user=Depends(admin_user)):
    return update_doc("courses", course_id, {"is_published": False})

# Modules / topics
@router.get("/courses/{course_id}/modules")
def modules(course_id: str, user=Depends(admin_user)):
    if not find_by_id("courses", course_id): raise HTTPException(404, "Course not found")
    return [clean(x) for x in get_db().topics.find({"course_id": course_id}).sort("order", 1)]

@router.post("/courses/{course_id}/modules")
def create_module(course_id: str, data: dict, user=Depends(admin_user)):
    if not find_by_id("courses", course_id): raise HTTPException(404, "Course not found")
    d = dict(data)
    d["course_id"] = course_id
    d.setdefault("name", d.get("title", ""))
    if not d["name"]: raise HTTPException(422, "Module/topic name is required")
    d.setdefault("title", d["name"])
    d.setdefault("description", "")
    d.setdefault("learning_objectives", [])
    d.setdefault("estimated_minutes", 0)
    d.setdefault("order", get_db().topics.count_documents({"course_id": course_id}) + 1)
    d.setdefault("is_published", True)
    return create_doc("topics", d, True)

@router.get("/modules/{module_id}")
def module(module_id: str, user=Depends(admin_user)):
    x = find_by_id("topics", module_id)
    if not x: raise HTTPException(404, "Module not found")
    return clean(x)

@router.put("/modules/{module_id}")
def update_module(module_id: str, data: dict, user=Depends(admin_user)):
    return update_doc("topics", module_id, data)

@router.delete("/modules/{module_id}")
def delete_module(module_id: str, user=Depends(admin_user)):
    old = find_by_id("topics", module_id)
    if not old: raise HTTPException(404, "Module not found")
    get_db().topics.delete_one({"_id": old["_id"]})
    get_db().lessons.delete_many({"topic_id": module_id})
    return {"message": "Module and lessons deleted"}

# Lessons
@router.get("/modules/{module_id}/lessons")
def lessons(module_id: str, user=Depends(admin_user)):
    if not find_by_id("topics", module_id): raise HTTPException(404, "Module not found")
    return [clean(x) for x in get_db().lessons.find({"topic_id": module_id}).sort("order", 1)]

@router.post("/modules/{module_id}/lessons")
def create_lesson(module_id: str, data: dict, user=Depends(admin_user)):
    module = find_by_id("topics", module_id)
    if not module: raise HTTPException(404, "Module not found")
    d = dict(data)
    d["topic_id"] = module_id
    d["course_id"] = module.get("course_id")
    d.setdefault("title", d.get("name", ""))
    d.setdefault("name", d["title"])
    if not d["title"]: raise HTTPException(422, "Lesson title is required")
    d.setdefault("description", "")
    d.setdefault("content", "")
    d.setdefault("order", get_db().lessons.count_documents({"topic_id": module_id}) + 1)
    d.setdefault("duration_minutes", 10)
    d.setdefault("resources", [])
    d.setdefault("is_published", True)
    return create_doc("lessons", d, True)

@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: str, user=Depends(admin_user)):
    x = find_by_id("lessons", lesson_id)
    if not x: raise HTTPException(404, "Lesson not found")
    return clean(x)

@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: str, data: dict, user=Depends(admin_user)):
    return update_doc("lessons", lesson_id, data)

@router.delete("/lessons/{lesson_id}")
def delete_lesson(lesson_id: str, user=Depends(admin_user)):
    return delete_doc("lessons", lesson_id)

@router.post("/lessons/{lesson_id}/publish")
def publish_lesson(lesson_id: str, user=Depends(admin_user)):
    return update_doc("lessons", lesson_id, {"is_published": True})

@router.post("/lessons/{lesson_id}/unpublish")
def unpublish_lesson(lesson_id: str, user=Depends(admin_user)):
    return update_doc("lessons", lesson_id, {"is_published": False})

# Questions
@router.get("/questions")
def questions(search: str | None = None, difficulty: str | None = None, user=Depends(admin_user)):
    conditions = []
    if search: conditions.append({"question": {"$regex": search, "$options": "i"}})
    if difficulty: conditions.append({"difficulty": difficulty.lower()})
    q = conditions[0] if len(conditions) == 1 else {"$and": conditions} if conditions else {}
    return [clean(x) for x in get_db().questions.find(q).sort("created_at", -1)]

@router.post("/questions")
def create_question(data: dict, user=Depends(admin_user)):
    d = dict(data)
    d.setdefault("question_type", "mcq")
    d.setdefault("difficulty", "easy")
    d.setdefault("marks", 1)
    d.setdefault("negative_marks", 0)
    d.setdefault("options", [])
    d.setdefault("correct_answer", d.get("answer", 0))
    d.setdefault("explanation", "")
    d.setdefault("is_published", True)
    if not d.get("question"): raise HTTPException(422, "Question is required")
    if d["question_type"] == "mcq" and len(d["options"]) < 2: raise HTTPException(422, "MCQ requires at least two options")
    return create_doc("questions", d, True)

@router.get("/questions/{question_id}")
def question(question_id: str, user=Depends(admin_user)):
    x = find_by_id("questions", question_id)
    if not x: raise HTTPException(404, "Question not found")
    return clean(x)

@router.put("/questions/{question_id}")
def update_question(question_id: str, data: dict, user=Depends(admin_user)):
    return update_doc("questions", question_id, data)

@router.delete("/questions/{question_id}")
def delete_question(question_id: str, user=Depends(admin_user)):
    return delete_doc("questions", question_id)

# Quizzes
@router.get("/quizzes")
def quizzes(search: str | None = None, user=Depends(admin_user)):
    q = {}
    if search:
        q = {"$or": [{"title": {"$regex": search, "$options": "i"}}, {"name": {"$regex": search, "$options": "i"}}]}
    return [clean(x) for x in get_db().quizzes.find(q).sort("created_at", -1)]

@router.post("/quizzes")
def create_quiz(data: dict, user=Depends(admin_user)):
    d = dict(data)
    d.setdefault("title", d.get("name", ""))
    if not d["title"]: raise HTTPException(422, "Quiz title is required")
    d.setdefault("name", d["title"])
    d.setdefault("description", "")
    d.setdefault("course_id", None)
    d.setdefault("module_id", None)
    d.setdefault("duration_minutes", 15)
    d.setdefault("passing_percentage", 60)
    d.setdefault("max_attempts", 3)
    d.setdefault("question_ids", [])
    d.setdefault("is_published", False)
    return create_doc("quizzes", d, True)

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id: str, user=Depends(admin_user)):
    x = find_by_id("quizzes", quiz_id)
    if not x: raise HTTPException(404, "Quiz not found")
    return clean(x)

@router.put("/quizzes/{quiz_id}")
def update_quiz(quiz_id: str, data: dict, user=Depends(admin_user)):
    return update_doc("quizzes", quiz_id, data)

@router.delete("/quizzes/{quiz_id}")
def delete_quiz(quiz_id: str, user=Depends(admin_user)):
    return delete_doc("quizzes", quiz_id)

@router.post("/quizzes/{quiz_id}/publish")
def publish_quiz(quiz_id: str, user=Depends(admin_user)):
    return update_doc("quizzes", quiz_id, {"is_published": True})

@router.post("/quizzes/{quiz_id}/unpublish")
def unpublish_quiz(quiz_id: str, user=Depends(admin_user)):
    return update_doc("quizzes", quiz_id, {"is_published": False})

@router.post("/quizzes/{quiz_id}/questions")
def add_quiz_questions(quiz_id: str, data: dict, user=Depends(admin_user)):
    quiz = find_by_id("quizzes", quiz_id)
    if not quiz: raise HTTPException(404, "Quiz not found")
    ids = list(quiz.get("question_ids", []) or [])
    for qid in data.get("question_ids", []) or []:
        if not find_by_id("questions", str(qid)): raise HTTPException(404, f"Question not found: {qid}")
        if str(qid) not in [str(x) for x in ids]: ids.append(qid)
    return update_doc("quizzes", quiz_id, {"question_ids": ids})

@router.delete("/quizzes/{quiz_id}/questions/{question_id}")
def remove_quiz_question(quiz_id: str, question_id: str, user=Depends(admin_user)):
    quiz = find_by_id("quizzes", quiz_id)
    if not quiz: raise HTTPException(404, "Quiz not found")
    ids = [x for x in quiz.get("question_ids", []) if str(x) != str(question_id)]
    return update_doc("quizzes", quiz_id, {"question_ids": ids})

# Convenience: create a question and attach it to a quiz in one step.
@router.post("/quizzes/{quiz_id}/questions/create")
def create_question_for_quiz(quiz_id: str, data: dict, user=Depends(admin_user)):
    if not find_by_id("quizzes", quiz_id): raise HTTPException(404, "Quiz not found")
    d = dict(data)
    d.setdefault("question_type", "mcq")
    d.setdefault("difficulty", "easy")
    d.setdefault("marks", 1)
    d.setdefault("negative_marks", 0)
    d.setdefault("options", [])
    d.setdefault("correct_answer", d.get("answer", 0))
    d.setdefault("explanation", "")
    d.setdefault("is_published", True)
    if not d.get("question") or len(d.get("options", [])) < 2:
        raise HTTPException(422, "Question and at least two options are required")
    q = create_doc("questions", d, True)
    quiz = find_by_id("quizzes", quiz_id)
    ids = list(quiz.get("question_ids", []) or [])
    ids.append(q["_id"])
    update_doc("quizzes", quiz_id, {"question_ids": ids})
    return {"question": q, "quiz": clean(find_by_id("quizzes", quiz_id))}


# Bulk quiz JSON import
BULK_QUIZ_BATCH_SIZE = 50


def _text_value(value, language="english"):
    if isinstance(value, dict):
        preferred = value.get(language)
        if preferred is not None:
            return str(preferred).strip()
        for key in ("english", "en", "hindi", "hi"):
            if value.get(key) is not None:
                return str(value[key]).strip()
        return ""
    return str(value or "").strip()


def _bilingual_value(value):
    if not isinstance(value, dict):
        text = str(value or "").strip()
        return {"english": text, "hindi": text}
    return {"english": _text_value(value, "english"), "hindi": _text_value(value, "hindi")}


def _normalize_options(options, options_hindi=None, options_bilingual=None):
    """Accept legacy single-language and bilingual option formats.

    Supported input forms:
      1. "options": ["A", "B", "C", "D"]
      2. "options": {"english": [...], "hindi": [...]}
      3. "options": [...], "options_hindi": [...]
      4. "options_bilingual": [{"english": "...", "hindi": "..."}, ...]
    """
    english = []
    hindi = []

    if isinstance(options, dict):
        english = list(options.get("english") or options.get("en") or [])
        hindi = list(options.get("hindi") or options.get("hi") or [])
    elif isinstance(options, list):
        english = list(options)

    if isinstance(options_hindi, list):
        hindi = list(options_hindi)

    if isinstance(options_bilingual, list) and options_bilingual:
        bilingual_english = []
        bilingual_hindi = []
        for item in options_bilingual:
            if isinstance(item, dict):
                bilingual_english.append(_text_value(item, "english"))
                bilingual_hindi.append(_text_value(item, "hindi"))
            else:
                bilingual_english.append(str(item or "").strip())
                bilingual_hindi.append(str(item or "").strip())
        if bilingual_english:
            english = bilingual_english
        if bilingual_hindi:
            hindi = bilingual_hindi

    return english, hindi


def _normalize_correct_answer(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value or "").strip().upper()
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    if text in mapping:
        return mapping[text]
    try:
        return int(text)
    except Exception:
        return -1


def _normalize_question(raw, question_number):
    if not isinstance(raw, dict):
        raise ValueError(f"Question {question_number}: question must be an object")
    question_value = raw.get("question", "")
    question_hindi = raw.get("question_hindi")
    if question_hindi is not None and not isinstance(question_value, dict):
        question_value = {"english": question_value, "hindi": question_hindi}
    question_i18n = _bilingual_value(question_value)
    if not (question_i18n["english"] or question_i18n["hindi"]):
        raise ValueError(f"Question {question_number}: question is required")

    english_options, hindi_options = _normalize_options(
        raw.get("options", []),
        raw.get("options_hindi"),
        raw.get("options_bilingual"),
    )
    if not english_options and not hindi_options:
        raise ValueError(f"Question {question_number}: options are required")
    if not english_options:
        english_options = list(hindi_options)
    if not hindi_options:
        hindi_options = list(english_options)
    if len(english_options) != 4 or len(hindi_options) != 4:
        raise ValueError(f"Question {question_number}: exactly 4 options are required")

    english_options = [str(x).strip() for x in english_options]
    hindi_options = [str(x).strip() for x in hindi_options]
    if any(not x for x in english_options + hindi_options):
        raise ValueError(f"Question {question_number}: empty option is not allowed")

    def duplicate(values):
        normalized = [" ".join(v.casefold().split()) for v in values]
        return len(normalized) != len(set(normalized))

    if duplicate(english_options):
        raise ValueError(f"Question {question_number}: duplicate English options are not allowed")
    if duplicate(hindi_options):
        raise ValueError(f"Question {question_number}: duplicate Hindi options are not allowed")

    correct_answer = _normalize_correct_answer(raw.get("correct_answer", raw.get("answer")))
    if correct_answer not in (0, 1, 2, 3):
        raise ValueError(f"Question {question_number}: correct_answer must be 0, 1, 2, or 3")

    explanation_value = raw.get("explanation", "")
    explanation_hindi = raw.get("explanation_hindi")
    if explanation_hindi is not None and not isinstance(explanation_value, dict):
        explanation_value = {"english": explanation_value, "hindi": explanation_hindi}
    explanation_i18n = _bilingual_value(explanation_value)
    difficulty = str(raw.get("difficulty", "medium") or "medium").strip().lower()
    marks = raw.get("marks", raw.get("points", 1))
    negative_marks = raw.get("negative_marks", 0)
    try:
        marks = float(marks)
        marks = int(marks) if marks.is_integer() else marks
    except Exception:
        marks = 1
    try:
        negative_marks = float(negative_marks)
        negative_marks = int(negative_marks) if negative_marks.is_integer() else negative_marks
    except Exception:
        negative_marks = 0

    return {
        "question": question_i18n["english"] or question_i18n["hindi"],
        "question_hindi": question_i18n["hindi"] or question_i18n["english"],
        "question_i18n": question_i18n,
        "question_type": str(raw.get("question_type", "mcq") or "mcq").lower(),
        "options": english_options,
        "options_hindi": hindi_options,
        "options_bilingual": [
            {"english": english_options[i], "hindi": hindi_options[i]}
            for i in range(4)
        ],
        "correct_answer": correct_answer,
        "explanation": explanation_i18n["english"],
        "explanation_hindi": explanation_i18n["hindi"],
        "explanation_i18n": explanation_i18n,
        "difficulty": difficulty,
        "marks": marks,
        "points": marks,
        "negative_marks": negative_marks,
        "is_published": False,
    }


def _validate_bulk_quiz(raw_quiz, quiz_number):
    if not isinstance(raw_quiz, dict):
        raise ValueError(f"Quiz {quiz_number}: quiz must be an object")
    title = str(raw_quiz.get("title", raw_quiz.get("name", "")) or "").strip()
    if not title:
        raise ValueError(f"Quiz {quiz_number}: title is required")
    questions = raw_quiz.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"Quiz {quiz_number} ({title}): questions must be a non-empty array")

    normalized_questions = []
    seen_questions = set()
    for index, raw_question in enumerate(questions, 1):
        normalized = _normalize_question(raw_question, index)
        key = " ".join(normalized["question"].casefold().split())
        if key in seen_questions:
            raise ValueError(f"Quiz {quiz_number} ({title}): duplicate question {index} is not allowed")
        seen_questions.add(key)
        normalized_questions.append(normalized)

    try:
        duration = max(1, int(raw_quiz.get("duration_minutes", 25)))
    except Exception:
        duration = 25
    try:
        passing = min(100, max(0, int(raw_quiz.get("passing_percentage", 60))))
    except Exception:
        passing = 60
    return {
        "title": title,
        "subject": str(raw_quiz.get("subject", "Reasoning") or "").strip(),
        "topic": str(raw_quiz.get("topic", "General") or "").strip(),
        "description": str(raw_quiz.get("description", "") or "").strip(),
        "passing_percentage": passing,
        "duration_minutes": duration,
        "questions": normalized_questions,
    }


@router.post("/bulk/quiz")
def bulk_quiz(data: dict | list, user=Depends(admin_user)):
    """Create at most 50 quiz drafts per request; safe to retry."""
    if isinstance(data, list):
        raw_quizzes, batch_number, total_batches = data, 1, 1
    elif isinstance(data, dict):
        raw_quizzes = data.get("quizzes", data.get("items", []))
        batch_number = int(data.get("batch_number", 1) or 1)
        total_batches = int(data.get("total_batches", 1) or 1)
    else:
        raise HTTPException(422, "Bulk quiz payload must be an array or an object containing quizzes")

    if not isinstance(raw_quizzes, list) or not raw_quizzes:
        raise HTTPException(422, "At least one quiz is required")
    if len(raw_quizzes) > BULK_QUIZ_BATCH_SIZE:
        raise HTTPException(422, f"Maximum {BULK_QUIZ_BATCH_SIZE} quizzes are allowed per batch")

    db = get_db()
    created, skipped, failed = [], [], []
    for quiz_index, raw_quiz in enumerate(raw_quizzes, 1):
        try:
            quiz_data = _validate_bulk_quiz(raw_quiz, quiz_index)
            title, subject, topic = quiz_data["title"], quiz_data["subject"], quiz_data["topic"]
            existing = db.quizzes.find_one({"title": title, "subject": subject, "topic": topic})
            if existing:
                skipped.append({"index": quiz_index, "title": title, "quiz_id": str(existing.get("_id")), "reason": "Quiz already exists with the same title, subject and topic"})
                continue

            question_ids = []
            try:
                for question in quiz_data["questions"]:
                    question_doc = make_doc({**question, "subject": subject, "topic": topic}, True)
                    db.questions.insert_one(question_doc)
                    question_ids.append(question_doc["_id"])

                quiz_doc = make_doc({
                "title": title,
                "name": title,
                "subject": subject,
                "topic": topic,
                "description": quiz_data["description"],
                "passing_percentage": quiz_data["passing_percentage"],
                "duration_minutes": quiz_data["duration_minutes"],
                "max_attempts": 3,
                "question_ids": question_ids,
                "question_count": len(question_ids),
                "is_published": False,
                "bulk_import": True,
                "bulk_import_batch": batch_number,
                "bulk_import_by": str(user.get("_id")),
                }, True)
                db.quizzes.insert_one(quiz_doc)
                created.append({"index": quiz_index, "title": title, "quiz_id": str(quiz_doc["_id"]), "question_count": len(question_ids)})
            except Exception:
                # Do not leave orphan questions behind if the quiz document
                # cannot be written after question validation succeeds.
                if question_ids:
                    db.questions.delete_many({"_id": {"$in": question_ids}})
                raise
        except Exception as exc:
            failed.append({"index": quiz_index, "title": str(raw_quiz.get("title", raw_quiz.get("name", ""))) if isinstance(raw_quiz, dict) else "", "error": str(exc)})

    return {
        "message": f"Batch {batch_number}/{total_batches} processed",
        "batch_number": batch_number,
        "total_batches": total_batches,
        "batch_size": len(raw_quizzes),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "created": created,
        "skipped": skipped,
        "failed": failed,
    }

# Students -- explicit endpoints, no generic /users dependency.
@router.get("/students")
def students(search: str | None = None, user=Depends(admin_user)):
    q = {"role": "student"}
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"email": {"$regex": search, "$options": "i"}}]
    return [clean(x) for x in get_db().users.find(q, {"password_hash": 0}).sort("created_at", -1)]

@router.get("/students/{student_id}")
def student(student_id: str, user=Depends(admin_user)):
    x = find_by_id("users", student_id)
    if not x or x.get("role") != "student": raise HTTPException(404, "Student not found")
    x.pop("password_hash", None)
    return clean(x)

@router.put("/students/{student_id}/status")
def student_status(student_id: str, data: dict, user=Depends(admin_user)):
    x = find_by_id("users", student_id)
    if not x or x.get("role") != "student": raise HTTPException(404, "Student not found")
    active = bool(data.get("is_active", True))
    get_db().users.update_one({"_id": x["_id"]}, {"$set": {"is_active": active, "updated_at": now()}})
    return {"id": str(x["_id"]), "is_active": active}


# Root admin: manage staff/admin accounts with explicit roles.
@router.get("/users/admins")
def list_admins(user=Depends(root_admin_user)):
    roles = {"root_admin", "admin", "content_admin", "instructor", "support_admin"}
    return [clean(x) for x in get_db().users.find({"role": {"$in": list(roles)}}, {"password_hash": 0}).sort("created_at", -1)]

@router.post("/users/admins")
def create_admin(data: dict, user=Depends(root_admin_user)):
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "admin")).strip()
    allowed = {"admin", "content_admin", "instructor", "support_admin"}
    if not name or len(name) < 2: raise HTTPException(422, "Name is required")
    if not email or "@" not in email: raise HTTPException(422, "Valid email is required")
    if len(password) < 8: raise HTTPException(422, "Password must contain at least 8 characters")
    if role not in allowed: raise HTTPException(422, "Invalid admin role")
    db = get_db()
    if db.users.find_one({"email": email}): raise HTTPException(409, "Email already registered")
    d = {"_id": uuid.uuid4().hex, "name": name, "email": email, "password_hash": hash_password(password), "role": role, "is_active": True, "auth_provider": "password", "created_at": now(), "updated_at": now()}
    db.users.insert_one(d)
    d.pop("password_hash", None)
    return clean(d)

@router.put("/users/admins/{user_id}/status")
def admin_status(user_id: str, data: dict, user=Depends(root_admin_user)):
    x = find_by_id("users", user_id)
    if not x or x.get("role") == "student": raise HTTPException(404, "Admin user not found")
    if str(x["_id"]) == str(user["_id"]): raise HTTPException(400, "Root admin cannot disable itself")
    active = bool(data.get("is_active", True))
    get_db().users.update_one({"_id": x["_id"]}, {"$set": {"is_active": active, "updated_at": now()}})
    return {"id": str(x["_id"]), "is_active": active}

@router.delete("/users/admins/{user_id}")
def delete_admin(user_id: str, user=Depends(root_admin_user)):
    x = find_by_id("users", user_id)
    if not x or x.get("role") == "student": raise HTTPException(404, "Admin user not found")
    if str(x["_id"]) == str(user["_id"]): raise HTTPException(400, "Root admin cannot delete itself")
    get_db().users.delete_one({"_id": x["_id"]})
    return {"message": "Admin user deleted"}
