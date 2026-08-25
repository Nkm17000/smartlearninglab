from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query

from app.core.security import current_user
from app.core.cache import cache
from app.db.mongo import get_db

router = APIRouter(prefix="/api/v1", tags=["Study Assistance"])

TTL_STUDY_ASSISTANCE = 30
TTL_STUDY_SEARCH = 30


def now():
    return datetime.now(timezone.utc)


def uid(user):
    return str(user["_id"])


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k != "password_hash"}
    if isinstance(value, list):
        return [clean(v) for v in value]
    try:
        from bson import ObjectId
        if isinstance(value, ObjectId):
            return str(value)
    except Exception:
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def user_variants(user_id):
    variants = [user_id]
    try:
        from bson import ObjectId
        if ObjectId.is_valid(user_id):
            variants.append(ObjectId(user_id))
    except Exception:
        pass
    return variants


def first_text(item, *keys, default=""):
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return default


@router.get("/study-assistance")
def study_assistance(user=Depends(current_user)):
    """Return one compact, rule-based study-assistance payload.

    No LLM, external AI API, vector database or third-party service is used.
    All recommendations are derived from the student's existing learning data.
    """
    user_id = uid(user)
    key = f"study_assistance:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    db = get_db()
    variants = user_variants(user_id)

    progress = list(db.progress.find(
        {"user_id": {"$in": variants}},
        {"course_id": 1, "lesson_id": 1, "completed": 1, "completed_at": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(300))
    completed = [p for p in progress if p.get("completed")]
    completed_by_course = defaultdict(set)
    for item in completed:
        completed_by_course[str(item.get("course_id"))].add(str(item.get("lesson_id")))

    enrollments = list(db.enrollments.find(
        {"user_id": {"$in": variants}, "status": "active"},
        {"course_id": 1, "updated_at": 1, "created_at": 1},
    ).sort("updated_at", -1).limit(20))
    course_ids = [str(x.get("course_id")) for x in enrollments if x.get("course_id") is not None]
    course_lookup_ids = list(course_ids)
    try:
        from bson import ObjectId
        for value in course_ids:
            if ObjectId.is_valid(value):
                course_lookup_ids.append(ObjectId(value))
    except Exception:
        pass

    courses = list(db.courses.find(
        {"_id": {"$in": course_lookup_ids}, "is_published": {"$ne": False}},
        {"name": 1, "title": 1, "short_description": 1, "description": 1, "level": 1, "category": 1, "is_free": 1},
    )) if course_ids else []
    course_by_id = {str(x.get("_id")): x for x in courses}

    lessons = list(db.lessons.find(
        {"course_id": {"$in": course_lookup_ids}, "is_published": True},
        {"_id": 1, "course_id": 1, "topic_id": 1, "title": 1, "name": 1, "description": 1, "order": 1, "duration_minutes": 1, "content": 1},
    ).sort("order", 1)) if course_ids else []
    lessons_by_course = defaultdict(list)
    for lesson in lessons:
        lessons_by_course[str(lesson.get("course_id"))].append(lesson)

    course_cards = []
    continue_learning = None
    for course_id in course_ids:
        course = course_by_id.get(course_id)
        if not course:
            continue
        course_lessons = lessons_by_course.get(course_id, [])
        done_ids = completed_by_course.get(course_id, set())
        total = len(course_lessons)
        done = sum(1 for lesson in course_lessons if str(lesson.get("_id")) in done_ids)
        pct = round(done * 100 / total, 1) if total else 0
        next_lesson = next((x for x in course_lessons if str(x.get("_id")) not in done_ids), None)
        item = clean(course)
        item.update({
            "course_id": course_id,
            "progress_percentage": pct,
            "completed_lessons": done,
            "total_lessons": total,
            "next_lesson": clean(next_lesson) if next_lesson else None,
        })
        course_cards.append(item)
        if continue_learning is None and next_lesson:
            continue_learning = {
                "course_id": course_id,
                "course_title": first_text(course, "name", "title", default="Course"),
                "lesson_id": str(next_lesson.get("_id")),
                "lesson_title": first_text(next_lesson, "title", "name", default="Next lesson"),
                "progress_percentage": pct,
            }

    attempts = list(db.test_attempts.find(
        {"user_id": {"$in": variants}, "status": "submitted"},
        {"test_id": 1, "result": 1, "submitted_at": 1, "created_at": 1},
    ).sort("submitted_at", -1).limit(50))
    quiz_ids = list({str(x.get("test_id")) for x in attempts if x.get("test_id") is not None})
    quizzes = list(db.quizzes.find(
        {"_id": {"$in": quiz_ids}},
        {"title": 1, "name": 1, "course_id": 1, "category": 1},
    )) if quiz_ids else []
    quiz_by_id = {str(x.get("_id")): x for x in quizzes}

    scores = [float((x.get("result") or {}).get("percentage", 0) or 0) for x in attempts]
    average = round(sum(scores) / len(scores), 1) if scores else 0

    mistakes = []
    weak = defaultdict(lambda: {"wrong": 0, "total": 0, "title": ""})
    for attempt in attempts:
        result = attempt.get("result") or {}
        quiz_id = str(attempt.get("test_id") or "")
        quiz = quiz_by_id.get(quiz_id) or {}
        topic = first_text(quiz, "category", default="General practice")
        for detail in result.get("details", []) or []:
            weak[topic]["total"] += 1
            if not detail.get("correct"):
                weak[topic]["wrong"] += 1
                if len(mistakes) < 12:
                    mistakes.append({
                        "quiz_id": quiz_id,
                        "quiz_title": first_text(quiz, "title", "name", default="Quiz"),
                        "question_id": str(detail.get("question_id", "")),
                        "question": first_text(detail, "question", default="Review this question"),
                        "submitted_text": detail.get("submitted_text"),
                        "correct_answer_text": detail.get("correct_answer_text"),
                        "explanation": detail.get("explanation", ""),
                    })

    weak_topics = []
    for topic, values in weak.items():
        if values["total"] <= 0:
            continue
        score = round((values["total"] - values["wrong"]) * 100 / values["total"], 1)
        weak_topics.append({"topic": topic, "score": score, "wrong": values["wrong"], "total": values["total"]})
    weak_topics.sort(key=lambda x: (x["score"], -x["wrong"]))

    due_cards = list(db.flashcards.find(
        {"user_id": {"$in": variants}, "due_at": {"$lte": now()}},
        {"front": 1, "back": 1, "course_id": 1, "due_at": 1, "repetitions": 1, "ease": 1},
    ).sort("due_at", 1).limit(12))
    flashcard_count = db.flashcards.count_documents({"user_id": {"$in": variants}})

    notes = list(db.notes.find(
        {"user_id": {"$in": variants}},
        {"_id": 1, "content": 1, "course_id": 1, "lesson_id": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(6))

    bookmarks = list(db.bookmarks.find(
        {"user_id": {"$in": variants}},
        {"_id": 1, "item_type": 1, "item_id": 1, "title": 1, "created_at": 1},
    ).sort("created_at", -1).limit(6))

    # Recent study history. activity_events is optional in older deployments.
    history = []
    try:
        history = list(db.activity_events.find(
            {"user_id": {"$in": variants}},
            {"type": 1, "action": 1, "title": 1, "created_at": 1},
        ).sort("created_at", -1).limit(12))
    except Exception:
        history = []
    if not history:
        for item in completed[:8]:
            history.append({
                "type": "lesson",
                "action": "completed",
                "title": "Lesson completed",
                "created_at": item.get("completed_at") or item.get("updated_at") or item.get("created_at"),
            })
        for item in attempts[:6]:
            history.append({
                "type": "quiz",
                "action": "submitted",
                "title": first_text(quiz_by_id.get(str(item.get("test_id"))) or {}, "title", "name", default="Quiz submitted"),
                "created_at": item.get("submitted_at") or item.get("created_at"),
            })
        history.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        history = history[:12]

    plan = []
    if continue_learning:
        plan.append({"type": "continue", "title": f"Continue {continue_learning['lesson_title']}", "subtitle": continue_learning["course_title"], "route": "lesson", "course_id": continue_learning["course_id"], "lesson_id": continue_learning["lesson_id"]})
    if due_cards:
        plan.append({"type": "revision", "title": f"Review {len(due_cards)} flashcards", "subtitle": "Cards are due for revision", "route": "flashcards"})
    if mistakes:
        plan.append({"type": "practice", "title": "Review your recent mistakes", "subtitle": f"{len(mistakes)} questions need another look", "route": "study-mistakes"})
    if weak_topics:
        plan.append({"type": "practice", "title": f"Practice {weak_topics[0]['topic']}", "subtitle": f"Current score {weak_topics[0]['score']}%", "route": "mock-test"})
    if not plan:
        plan.append({"type": "explore", "title": "Start a practice session", "subtitle": "Build your learning habit with a short test", "route": "mock-test"})
    plan = plan[:4]

    result = {
        "stats": {
            "courses": len(course_cards),
            "lessons_done": len(completed),
            "quiz_average": average,
            "tests_attempted": len(attempts),
            "flashcards_due": len(due_cards),
            "flashcards_total": flashcard_count,
        },
        "continue_learning": continue_learning,
        "today_plan": plan,
        "courses": course_cards[:5],
        "due_flashcards": clean(due_cards),
        "mistakes": mistakes,
        "weak_topics": weak_topics[:6],
        "notes": clean(notes),
        "bookmarks": clean(bookmarks),
        "history": clean(history),
        "recent_results": clean(attempts[:8]),
        "recommendations": [
            "Review due flashcards before starting a new topic.",
            "Practice the weakest topic after reviewing mistakes.",
            "Finish your current lesson before starting another course.",
        ],
    }
    cache.set(key, result, TTL_STUDY_ASSISTANCE)
    return result


@router.get("/study-assistance/search")
def study_search(q: str = Query("", min_length=1, max_length=100), limit: int = Query(8, ge=1, le=20), user=Depends(current_user)):
    """Search published courses, topics and lessons without an AI service."""
    query = q.strip()
    if not query:
        return {"courses": [], "topics": [], "lessons": []}

    safe = re.escape(query)
    regex = {"$regex": safe, "$options": "i"}
    key = f"study_search:{uid(user)}:{query.lower()}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    db = get_db()
    courses = list(db.courses.find(
        {"is_published": {"$ne": False}, "$or": [{"name": regex}, {"title": regex}, {"short_description": regex}, {"category": regex}]},
        {"name": 1, "title": 1, "short_description": 1, "category": 1, "level": 1},
    ).limit(limit))
    topics = list(db.topics.find(
        {"is_published": {"$ne": False}, "$or": [{"name": regex}, {"title": regex}, {"description": regex}]},
        {"name": 1, "title": 1, "description": 1, "course_id": 1},
    ).limit(limit))
    lessons = list(db.lessons.find(
        {"is_published": True, "$or": [{"title": regex}, {"name": regex}, {"description": regex}]},
        {"title": 1, "name": 1, "description": 1, "course_id": 1, "topic_id": 1, "duration_minutes": 1},
    ).limit(limit))

    result = {
        "courses": clean(courses),
        "topics": clean(topics),
        "lessons": clean(lessons),
    }
    cache.set(key, result, TTL_STUDY_SEARCH)
    return result
