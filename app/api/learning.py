from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_user
from app.db.mongo import get_db
from app.core.cache import (cache, TTL_DASHBOARD, TTL_COURSES, TTL_CATEGORIES,
                            TTL_FEATURED, TTL_COURSE_OVERVIEW, TTL_QUIZZES, TTL_RESULTS, TTL_PROGRESS, TTL_NOTES, TTL_ENROLLMENTS, TTL_LESSON_VIEW, TTL_LEARNING_SUMMARY, invalidate_user)

router = APIRouter(prefix="/api/v1", tags=["Student Learning"])

def clean(v, hide_answers=False):
    if isinstance(v, dict):
        out = {k: clean(x, hide_answers) for k, x in v.items() if k != "password_hash"}
        if hide_answers:
            for k in ("correct_answer", "answer", "explanation"):
                out.pop(k, None)
        return out
    if isinstance(v, list): return [clean(x, hide_answers) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v, ObjectId): return str(v)
    except Exception: pass
    if hasattr(v, "isoformat"): return v.isoformat()
    return v

def find_by_id(collection, item_id):
    db = get_db()
    x = db[collection].find_one({"_id": item_id})
    if x: return x
    try:
        from bson import ObjectId
        if ObjectId.is_valid(item_id): return db[collection].find_one({"_id": ObjectId(item_id)})
    except Exception: pass
    return None

def published(collection, item_id):
    """Return published content while enforcing the Course -> Topic -> Lesson tree.
    A child can never become visible to students while its parent is still draft.
    """
    x = find_by_id(collection, item_id)
    if not x:
        raise HTTPException(404, f"{collection.rstrip('s').capitalize()} not found")
    if x.get("is_published") is False:
        raise HTTPException(404, "Content not published")

    db = get_db()
    if collection == "topics":
        course_id = str(x.get("course_id", ""))
        course = find_by_id("courses", course_id) if course_id else None
        if not course or course.get("is_published") is False:
            raise HTTPException(404, "Parent course not published")

    elif collection == "lessons":
        course_id = str(x.get("course_id", ""))
        topic_id = str(x.get("topic_id", ""))
        course = find_by_id("courses", course_id) if course_id else None
        topic = find_by_id("topics", topic_id) if topic_id else None
        if not course or course.get("is_published") is False:
            raise HTTPException(404, "Parent course not published")
        if not topic or topic.get("is_published") is False:
            raise HTTPException(404, "Parent topic not published")

    elif collection == "quizzes":
        # A published quiz is its own student-facing publication boundary.
        # Older data may still contain a stale/draft course_id, and that must
        # not make an otherwise published quiz return 404. Course/module
        # relationships remain useful for navigation and filtering, but the
        # quiz itself must be openable once an admin explicitly publishes it.
        pass

    return x

def uid(user): return str(user["_id"])

@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    """Fast dashboard: batch-loads user data and enrolled-course content."""
    db = get_db(); user_id = uid(user)
    key = f"dashboard:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    progress = list(db.progress.find(
        {"user_id": user_id},
        {"course_id": 1, "lesson_id": 1, "completed": 1, "completed_at": 1, "updated_at": 1, "created_at": 1}
    ))
    completed_progress = [p for p in progress if p.get("completed")]
    completed_ids_by_course = {}
    for p in completed_progress:
        completed_ids_by_course.setdefault(str(p.get("course_id")), set()).add(str(p.get("lesson_id")))

    attempts = list(db.test_attempts.find(
        {"user_id": user_id, "status": "submitted"},
        {"result": 1, "submitted_at": 1, "created_at": 1, "updated_at": 1}
    ).sort("submitted_at", -1))
    percentages = [float((a.get("result") or {}).get("percentage", 0) or 0) for a in attempts]
    avg = round(sum(percentages) / len(percentages), 2) if percentages else 0

    enrollments = list(db.enrollments.find(
        {"user_id": user_id, "status": "active"},
        {"course_id": 1, "updated_at": 1, "created_at": 1}
    ).sort("updated_at", -1).limit(10))
    course_ids = [str(e.get("course_id")) for e in enrollments if e.get("course_id") is not None]

    courses = list(db.courses.find({"_id": {"$in": course_ids}})) if course_ids else []
    by_course = {str(c.get("_id")): c for c in courses}
    lessons = list(db.lessons.find(
        {"course_id": {"$in": course_ids}, "is_published": True},
        {"_id": 1, "course_id": 1, "title": 1, "name": 1, "order": 1}
    ).sort("order", 1)) if course_ids else []
    lessons_by_course = {}
    for lesson in lessons:
        lessons_by_course.setdefault(str(lesson.get("course_id")), []).append(lesson)

    enrolled_courses = []
    continue_learning = None
    for course_id in course_ids:
        c = by_course.get(course_id)
        if not c:
            continue
        course_lessons = lessons_by_course.get(course_id, [])
        done_ids = completed_ids_by_course.get(course_id, set())
        total = len(course_lessons)
        done = sum(1 for x in course_lessons if str(x.get("_id")) in done_ids)
        percentage = round(done * 100 / total, 2) if total else 0
        item = clean(c)
        item.update({"progress_percentage": percentage, "completed_lessons": done, "total_lessons": total})
        enrolled_courses.append(item)

        if continue_learning is None:
            next_lesson = next((x for x in course_lessons if str(x.get("_id")) not in done_ids), None)
            if next_lesson:
                continue_learning = {
                    "course_id": course_id,
                    "course_title": c.get("name") or c.get("title") or "Course",
                    "lesson_id": str(next_lesson.get("_id")),
                    "lesson_title": next_lesson.get("title") or next_lesson.get("name") or "Next lesson",
                    "progress_percentage": percentage,
                }

    today = datetime.now(timezone.utc).date()
    week_start = today - __import__('datetime').timedelta(days=today.weekday())
    active_dates = set()
    weekly_completed = 0
    for p in completed_progress:
        raw = p.get("completed_at") or p.get("updated_at") or p.get("created_at")
        try:
            d = raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
            active_dates.add(d)
            if d >= week_start:
                weekly_completed += 1
        except Exception:
            pass
    for a in attempts:
        raw = a.get("submitted_at") or a.get("updated_at") or a.get("created_at")
        try:
            active_dates.add(raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date())
        except Exception:
            pass
    for e in enrollments:
        raw = e.get("updated_at") or e.get("created_at")
        try:
            active_dates.add(raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date())
        except Exception:
            pass

    streak = 0
    cursor = today
    while cursor in active_dates:
        streak += 1
        cursor -= __import__('datetime').timedelta(days=1)

    passed = sum(1 for a in attempts if (a.get("result") or {}).get("passed"))
    completed_courses = sum(1 for x in enrolled_courses if x.get("total_lessons") and x.get("completed_lessons", 0) >= x.get("total_lessons"))
    xp = len(completed_progress) * 10 + passed * 50 + len(attempts) * 5 + completed_courses * 100

    result = {
        "user": {"id": user_id, "name": user.get("name"), "email": user.get("email"), "role": user.get("role")},
        "courses_available": db.courses.count_documents({"is_published": True}),
        "lessons_completed": len(completed_progress),
        "quiz_attempts": len(attempts),
        "quiz_average": avg,
        "xp": xp,
        "streak": {"current": streak},
        "enrolled_courses": enrolled_courses,
        "continue_learning": continue_learning,
        "weekly_goal": {"target": 5, "completed": weekly_completed, "percentage": min(100, round(weekly_completed * 100 / 5))},
        "recent_quiz_results": [clean(x) for x in attempts[:5]],
    }
    cache.set(key, result, TTL_DASHBOARD)
    return result

@router.get("/home")
def home(user=Depends(current_user)):
    """Single network call for the student home screen. Each component is TTL-cached."""
    user_id = uid(user)
    key = f"home:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = {
        "dashboard": dashboard(user),
        "catalog": catalog_categories(user),
        "featured": catalog_featured(10, user),
        "quizzes": quizzes(user=user),
    }
    cache.set(key, result, TTL_DASHBOARD)
    return result

@router.get("/profile")
def profile(user=Depends(current_user)):
    return {"id": uid(user), "name": user.get("name",""), "email": user.get("email",""), "role": user.get("role","student"), "is_active": user.get("is_active",True)}

@router.get("/courses")
def courses(search: str | None = None, category: str | None = None, exam: str | None = None, level: str | None = None, language: str | None = None, free_only: bool = True, user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    key = f"courses:{user_id}:{search or ''}:{category or ''}:{exam or ''}:{level or ''}:{language or ''}:{free_only}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    q = {"is_published": True}
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"exam": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]
    if category: q["category"] = {"$regex": category, "$options": "i"}
    if exam: q["exam"] = {"$regex": exam, "$options": "i"}
    if level: q["level"] = {"$regex": level, "$options": "i"}
    if language: q["language"] = {"$regex": language, "$options": "i"}

    enrolled_ids = {str(x.get("course_id")) for x in db.enrollments.find({"user_id": user_id}, {"course_id": 1})}
    progress_docs = list(db.progress.find({"user_id": user_id}, {"course_id": 1, "lesson_id": 1, "completed": 1}))
    completed_by_course = {}
    for x in progress_docs:
        if x.get("completed"):
            completed_by_course[str(x.get("course_id"))] = completed_by_course.get(str(x.get("course_id")), 0) + 1

    courses_list = list(db.courses.find(q).sort([("featured", -1), ("created_at", -1)]))
    ids = [str(x.get("_id")) for x in courses_list]
    lesson_counts = {str(x["_id"]): x["n"] for x in db.lessons.aggregate([
        {"$match": {"course_id": {"$in": ids}, "is_published": True}},
        {"$group": {"_id": "$course_id", "n": {"$sum": 1}}}
    ])} if ids else {}
    quiz_counts = {str(x["_id"]): x["n"] for x in db.quizzes.aggregate([
        {"$match": {"course_id": {"$in": ids}, "is_published": True}},
        {"$group": {"_id": "$course_id", "n": {"$sum": 1}}}
    ])} if ids else {}
    resource_counts = {str(x["_id"]): x["n"] for x in db.course_resources.aggregate([
        {"$match": {"course_id": {"$in": ids}}},
        {"$group": {"_id": "$course_id", "n": {"$sum": 1}}}
    ])} if ids else {}

    items = []
    for course in courses_list:
        cid = str(course.get("_id")); total = lesson_counts.get(cid, 0); completed = completed_by_course.get(cid, 0)
        item = clean(course)
        item.update({
            "is_enrolled": cid in enrolled_ids,
            "lesson_count": total,
            "quiz_count": quiz_counts.get(cid, 0),
            "pdf_count": resource_counts.get(cid, 0),
            "progress_percentage": round(completed * 100 / total, 2) if total else 0,
        })
        items.append(item)
    cache.set(key, items, TTL_COURSES)
    return items

@router.get("/catalog/categories")
def catalog_categories(user=Depends(current_user)):
    key = "catalog:categories"
    cached = cache.get(key)
    if cached is not None:
        return cached
    db = get_db()
    result = {
        "categories": sorted(x for x in db.courses.distinct("category") if x),
        "exams": sorted(x for x in db.courses.distinct("exam") if x),
        "levels": sorted(x for x in db.courses.distinct("level") if x),
    }
    cache.set(key, result, TTL_CATEGORIES)
    return result

@router.get("/catalog/featured")
def catalog_featured(limit:int=Query(8,ge=1,le=30),user=Depends(current_user)):
    key = f"catalog:featured:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    db=get_db()
    result = {
        "courses": [clean(x) for x in db.courses.find({"is_published":True}).sort([("featured",-1),("created_at",-1)]).limit(limit)],
        "quizzes": [clean(x) for x in db.quizzes.find({"is_published":True}).sort([("featured",-1),("created_at",-1)]).limit(limit)],
    }
    cache.set(key, result, TTL_FEATURED)
    return result

@router.get("/lessons/{lesson_id}")
def student_lesson(lesson_id: str, user=Depends(current_user)):
    """Student lesson payload. One request replaces lesson + resources + course progress + notes + navigation calls."""
    user_id = uid(user)
    key = f"lesson_view:{user_id}:{lesson_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    lesson = published("lessons", lesson_id)
    db = get_db()
    course_id = str(lesson.get("course_id"))
    topic_id = str(lesson.get("topic_id"))

    resources = [clean(x) for x in db.lesson_resources.find(
        {"lesson_id": lesson_id},
        {"_id": 1, "title": 1, "url": 1, "type": 1, "duration_seconds": 1, "order": 1}
    ).sort("order", 1)]

    topic_rows = list(db.topics.find(
        {"course_id": course_id, "is_published": True}, {"_id": 1, "order": 1}
    ).sort("order", 1))
    topic_ids = [str(x.get("_id")) for x in topic_rows]
    topic_order = {str(x.get("_id")): i for i, x in enumerate(topic_rows)}
    nav_lessons = list(db.lessons.find(
        {"course_id": course_id, "topic_id": {"$in": topic_ids}, "is_published": True},
        {"_id": 1, "topic_id": 1, "title": 1, "name": 1, "order": 1}
    ).sort([("topic_id", 1), ("order", 1)])) if topic_ids else []

    course_lesson_ids = [str(x.get("_id")) for x in nav_lessons]
    completed = set()
    if course_lesson_ids:
        completed = {
            str(x.get("lesson_id"))
            for x in db.progress.find(
                {"user_id": user_id, "course_id": course_id, "completed": True},
                {"lesson_id": 1}
            )
        }

    total = len(course_lesson_ids)
    done = len(completed)
    progress = {
        "course_id": course_id,
        "total_lessons": total,
        "completed_lessons": done,
        "percentage": round(done * 100 / total, 2) if total else 0,
    }

    notes = [clean(x) for x in db.notes.find(
        {"user_id": user_id, "lesson_id": lesson_id},
        {"_id": 1, "title": 1, "content": 1, "note": 1, "lesson_id": 1, "course_id": 1, "created_at": 1, "updated_at": 1}
    ).sort("updated_at", -1).limit(1)]

    nav = []
    for x in nav_lessons:
        nav.append({
            "id": str(x.get("_id")),
            "topic_id": str(x.get("topic_id")),
            "title": x.get("title") or x.get("name") or "Lesson",
            "order": x.get("order", 0),
            "topic_order": topic_order.get(str(x.get("topic_id")), 0),
            "completed": str(x.get("_id")) in completed,
        })

    out = clean(lesson)
    out["resources"] = resources
    out["progress"] = progress
    out["note"] = notes[0] if notes else None
    out["navigation"] = nav
    out["course_id"] = course_id
    out["topic_id"] = topic_id
    cache.set(key, out, TTL_LESSON_VIEW)
    return out

@router.get("/courses/{course_id}/overview")
def course_overview(course_id:str,user=Depends(current_user)):
    key = f"course:overview:{uid(user)}:{course_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    c=published("courses",course_id); db=get_db()
    modules=[clean(x) for x in db.topics.find({"course_id":course_id,"is_published":True}).sort("order",1)]
    topic_ids=[str(x.get("_id")) for x in modules]
    lessons=[clean(x) for x in db.lessons.find({"course_id":course_id,"topic_id":{"$in":topic_ids},"is_published":True}).sort([("topic_id",1),("order",1)])]
    quizzes=[clean(x) for x in db.quizzes.find({"course_id":course_id,"is_published":True}).sort("created_at",-1)]
    topic_names={str(x.get("_id")):(x.get("title") or x.get("name") or "Topic") for x in modules}
    lesson_ids=[str(x.get("_id")) for x in lessons]
    resources_by_lesson={}
    if lesson_ids:
        for r in db.lesson_resources.find({"lesson_id":{"$in":lesson_ids}}).sort("order",1):
            resources_by_lesson.setdefault(str(r.get("lesson_id")), []).append(clean(r))
    for lesson in lessons:
        lesson["topic_title"]=topic_names.get(str(lesson.get("topic_id")),"Topic")
        lesson["resources"]=resources_by_lesson.get(str(lesson.get("_id")),[])
    course_out=clean(c)
    course_out["resources"]=clean(list(db.course_resources.find({"course_id":course_id}).sort("order",1)))
    user_id = uid(user)
    completed_ids = {
        str(x.get("lesson_id")) for x in db.progress.find(
            {"user_id": user_id, "course_id": course_id, "completed": True}, {"lesson_id": 1}
        )
    }
    total_lessons = len(lessons)
    completed_lessons = sum(1 for x in lessons if str(x.get("_id")) in completed_ids)
    reviews = [clean(x) for x in db.course_reviews.find({"course_id": course_id}).sort("created_at", -1).limit(20)]
    bookmarked = bool(db.bookmarks.find_one({"user_id": user_id, "item_type": "course", "item_id": course_id}, {"_id": 1}))
    course_out["resources"] = course_out.get("resources", [])
    course_out["progress_percentage"] = round(completed_lessons * 100 / total_lessons, 2) if total_lessons else 0
    result={
        "course":course_out,
        "modules":modules,
        "lessons":lessons,
        "quizzes":quizzes,
        "resources":course_out["resources"],
        "completed_lesson_ids":sorted(completed_ids),
        "progress":{"course_id":course_id,"total_lessons":total_lessons,"completed_lessons":completed_lessons,"percentage":course_out["progress_percentage"]},
        "bookmarked":bookmarked,
        "reviews":reviews,
    }
    cache.set(key,result,TTL_COURSE_OVERVIEW)
    return result

@router.get("/enrollments")
def enrollments(user=Depends(current_user)):
    user_id = uid(user); key = f"enrollments:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().enrollments.find({"user_id":user_id}).sort("created_at",-1)]
    cache.set(key, result, TTL_ENROLLMENTS)
    return result

@router.get("/progress")
def progress(user=Depends(current_user)):
    user_id = uid(user); key = f"progress:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().progress.find({"user_id":user_id}).sort("updated_at",-1)]
    cache.set(key, result, TTL_PROGRESS)
    return result

@router.get("/courses/{course_id}/progress")
def course_progress(course_id: str, user=Depends(current_user)):
    user_id=uid(user)
    key=f"course_progress:{user_id}:{course_id}"
    cached=cache.get(key)
    if cached is not None: return cached
    published("courses",course_id); db=get_db()
    topic_ids=[str(x.get("_id")) for x in db.topics.find({"course_id":course_id,"is_published":True},{"_id":1})]
    lesson_ids=[str(x.get("_id")) for x in db.lessons.find({"course_id":course_id,"topic_id":{"$in":topic_ids},"is_published":True},{"_id":1})] if topic_ids else []
    total=len(lesson_ids)
    done=db.progress.count_documents({"user_id":user_id,"course_id":course_id,"completed":True,"lesson_id":{"$in":lesson_ids}}) if lesson_ids else 0
    result={"course_id":course_id,"total_lessons":total,"completed_lessons":done,"percentage":round(done*100/total,2) if total else 0}
    cache.set(key,result,TTL_PROGRESS)
    return result

@router.post("/progress")
def save_progress(data: dict, user=Depends(current_user)):
    course_id=data.get("course_id"); lesson_id=data.get("lesson_id")
    if not course_id or not lesson_id: raise HTTPException(422,"course_id and lesson_id are required")
    d=dict(data); d.update({"_id":uuid.uuid4().hex,"user_id":uid(user),"updated_at":datetime.now(timezone.utc)})
    db = get_db()
    db.progress.update_one({"user_id":uid(user),"lesson_id":lesson_id},{"$set":d},upsert=True)
    cache.delete_prefix(f"dashboard:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}")
    cache.delete_prefix(f"home:{uid(user)}")
    cache.delete_prefix(f"courses:{uid(user)}:")
    cache.delete_prefix(f"personalized:{uid(user)}")
    cache.delete_prefix(f"progress:{uid(user)}")
    cache.delete_prefix(f"course_progress:{uid(user)}:")
    cache.delete_prefix(f"course:overview:{uid(user)}:")
    cache.delete_prefix(f"lesson_view:{uid(user)}:")
    cache.delete_prefix(f"learning_summary:{uid(user)}")
    cache.delete_prefix(f"results:{uid(user)}")
    return clean(db.progress.find_one({"user_id":uid(user),"lesson_id":lesson_id}))

@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str, user=Depends(current_user)):
    l=published("lessons",lesson_id); db=get_db()
    d={"_id":uuid.uuid4().hex,"user_id":uid(user),"course_id":l.get("course_id"),"lesson_id":lesson_id,"completed":True,"completed_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    db.progress.update_one({"user_id":uid(user),"lesson_id":lesson_id},{"$set":d},upsert=True)
    db.notifications.insert_one({"_id": uuid.uuid4().hex, "user_id": uid(user), "title": "Lesson completed", "message": "Great job! You completed a lesson.", "read": False, "created_at": datetime.now(timezone.utc)})
    cache.delete_prefix(f"dashboard:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}")
    cache.delete_prefix(f"home:{uid(user)}")
    cache.delete_prefix(f"courses:{uid(user)}:")
    cache.delete_prefix(f"personalized:{uid(user)}")
    cache.delete_prefix(f"progress:{uid(user)}")
    cache.delete_prefix(f"course_progress:{uid(user)}:")
    cache.delete_prefix(f"course:overview:{uid(user)}:")
    cache.delete_prefix(f"lesson_view:{uid(user)}:")
    cache.delete_prefix(f"learning_summary:{uid(user)}")
    cache.delete_prefix(f"analytics:{uid(user)}")
    cache.delete_prefix(f"badges:{uid(user)}")
    return clean(d)

# Quiz discovery and attempt
@router.get("/learning/summary")
def learning_summary(user=Depends(current_user)):
    """Single payload for My Learning: courses, progress, results and learning path."""
    user_id=uid(user)
    key=f"learning_summary:{user_id}"
    cached=cache.get(key)
    if cached is not None: return cached
    db=get_db()
    courses_data=courses(user=user)
    progress_data=[clean(x) for x in db.progress.find({"user_id":user_id}).sort("updated_at",-1)]
    results_data=[clean(x) for x in db.test_attempts.find({"user_id":user_id,"status":"submitted"}).sort("submitted_at",-1).limit(100)]
    from app.api.features import personalized_path
    path_data=personalized_path(user)
    result={"courses":courses_data,"progress":progress_data,"results":results_data,"path":path_data}
    cache.set(key,result,TTL_LEARNING_SUMMARY)
    return result

@router.get("/quizzes")
def quizzes(course_id: str|None=None, module_id: str|None=None, user=Depends(current_user)):
    db=get_db()
    key=f"quizzes:{course_id or ''}:{module_id or ''}"
    cached=cache.get(key)
    if cached is not None:
        return cached
    q={"is_published":True}
    if course_id: q["course_id"]=course_id
    if module_id: q["module_id"]=module_id
    items=[]
    for x in db.quizzes.find(q).sort("created_at",-1):
        item=clean(x)
        ids=list(x.get("question_ids",[]) or [])
        item["question_count"]=len(ids)
        item["is_ready"]=bool(ids)
        items.append(item)
    cache.set(key,items,TTL_QUIZZES)
    return items

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id: str, user=Depends(current_user)):
    return clean(published("quizzes",quiz_id))

@router.get("/quizzes/{quiz_id}/questions")
def quiz_questions(quiz_id: str, user=Depends(current_user)):
    key=f"quiz_questions:{quiz_id}"
    cached=cache.get(key)
    if cached is not None: return cached
    qz=published("quizzes",quiz_id)
    ids=[str(x) for x in qz.get("question_ids",[])]
    # The quiz itself is the publication boundary.  Bulk-imported questions
    # may still be draft records until the admin publishes the quiz. Once the
    # quiz is published, return its attached questions in quiz order while
    # still hiding the answer/explanation from the student.
    if not ids:
        return []
    found = list(get_db().questions.find({"_id": {"$in": ids}}))
    by = {str(x["_id"]): x for x in found}
    result=[clean(by[i], hide_answers=True) for i in ids if i in by]
    cache.set(key,result,5*60)
    return result

@router.get("/quizzes/{quiz_id}/bundle")
def quiz_bundle(quiz_id: str, user=Depends(current_user)):
    """Single request for quiz metadata, questions and attempt state."""
    qz=published("quizzes",quiz_id); db=get_db(); user_id=uid(user)
    key=f"quiz_bundle:{user_id}:{quiz_id}"
    cached=cache.get(key)
    if cached is not None: return cached
    ids=[str(x) for x in qz.get("question_ids",[]) or []]
    found=list(db.questions.find({"_id":{"$in":ids}})) if ids else []
    by={str(x.get("_id")):x for x in found}
    questions=[clean(by[i],hide_answers=True) for i in ids if i in by]
    attempts=db.test_attempts.count_documents({"user_id":user_id,"test_id":quiz_id})
    active=db.test_attempts.find_one({"user_id":user_id,"test_id":quiz_id,"status":"started"}, sort=[("started_at",-1)])
    result={"quiz":clean(qz),"questions":questions,"attempts_used":attempts,"max_attempts":int(qz.get("max_attempts",3) or 3),"can_start":attempts<int(qz.get("max_attempts",3) or 3),
            "active_attempt":clean(active) if active else None}
    cache.set(key,result,60)
    return result

@router.post("/quizzes/{quiz_id}/start")
def start_quiz(quiz_id: str, user=Depends(current_user)):
    qz=published("quizzes",quiz_id); db=get_db(); user_id=uid(user)
    active=db.test_attempts.find_one({"user_id":user_id,"test_id":quiz_id,"status":"started"}, sort=[("started_at",-1)])
    if active:
        return {"attempt_id":str(active["_id"]),"quiz_id":quiz_id,"duration_minutes":qz.get("duration_minutes",15),"resumed":True,
                "answers":active.get("answers",{}) or {},"current_index":int(active.get("current_index",0) or 0)}
    attempts=db.test_attempts.count_documents({"user_id":user_id,"test_id":quiz_id})
    if attempts>=int(qz.get("max_attempts",3)): raise HTTPException(400,"Maximum attempts reached")
    a={"_id":uuid.uuid4().hex,"user_id":user_id,"test_id":quiz_id,"status":"started","started_at":datetime.now(timezone.utc),"answers":{},"current_index":0,"updated_at":datetime.now(timezone.utc)}
    db.test_attempts.insert_one(a)
    cache.delete_prefix(f"quiz_bundle:{user_id}:{quiz_id}")
    cache.delete_prefix(f"results:{user_id}")
    return {"attempt_id":a["_id"],"quiz_id":quiz_id,"duration_minutes":qz.get("duration_minutes",15),"resumed":False,"answers":{},"current_index":0}

@router.post("/quizzes/{quiz_id}/attempt/save")
def save_quiz_attempt(quiz_id: str, data: dict, user=Depends(current_user)):
    qz=published("quizzes",quiz_id)
    if not quiz_visible(qz): raise HTTPException(404,"Content not published")
    db=get_db(); user_id=uid(user)
    attempt_id=str(data.get("attempt_id") or "")
    if attempt_id:
        attempt=db.test_attempts.find_one({"_id":attempt_id,"user_id":user_id,"test_id":quiz_id,"status":"started"})
    else:
        attempt=db.test_attempts.find_one({"user_id":user_id,"test_id":quiz_id,"status":"started"}, sort=[("started_at",-1)])
    if not attempt: raise HTTPException(404,"Active quiz attempt not found")
    incoming=data.get("answers") or {}
    answers=dict(attempt.get("answers",{}) or {})
    answers.update(incoming)
    current_index=max(0,int(data.get("current_index",attempt.get("current_index",0)) or 0))
    db.test_attempts.update_one({"_id":attempt["_id"]},{"$set":{"answers":answers,"current_index":current_index,"updated_at":datetime.now(timezone.utc)}})
    cache.delete_prefix(f"quiz_bundle:{user_id}:{quiz_id}")
    return {"saved":True,"attempt_id":str(attempt["_id"]),"answers":answers,"current_index":current_index}

@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: str, data: dict, user=Depends(current_user)):
    qz=published("quizzes",quiz_id); db=get_db(); user_id=uid(user)
    answers=dict(data.get("answers",{}) or {})
    attempt_id=str(data.get("attempt_id") or "")
    attempt=None
    if attempt_id:
        attempt=db.test_attempts.find_one({"_id":attempt_id,"user_id":user_id,"test_id":quiz_id,"status":"started"})
    else:
        attempt=db.test_attempts.find_one({"user_id":user_id,"test_id":quiz_id,"status":"started"}, sort=[("started_at",-1)])
    if not attempt:
        raise HTTPException(400,"No active quiz attempt. Please start or resume the quiz.")
    merged=dict(attempt.get("answers",{}) or {})
    merged.update(answers)
    answers=merged
    ids=[str(x) for x in qz.get("question_ids",[])]
    # The quiz is already verified as published above. Grade only the
    # question ids attached to this quiz so bulk-imported questions work
    # immediately after the admin publishes the quiz.
    allq=list(db.questions.find({"_id": {"$in": ids}}))
    by={str(x["_id"]):x for x in allq}
    score=0.0; total=0.0; correct=0; wrong=0; details=[]
    for qid in ids:
        q=by.get(qid)
        if not q: continue
        marks=float(q.get("marks",1) or 1); neg=float(q.get("negative_marks",0) or 0); total+=marks
        submitted=answers.get(qid); expected=q.get("correct_answer",q.get("answer"))
        ok=submitted is not None and str(submitted)==str(expected)
        if ok: score+=marks; correct+=1
        elif submitted is not None: score-=neg; wrong+=1
        options=q.get("options",[]) or []
        def option_text(value):
            try:
                idx=int(value)
                if 0 <= idx < len(options):
                    opt=options[idx]
                    if isinstance(opt,dict):
                        return str(opt.get("text",opt.get("label",opt.get("value",opt.get("option",opt)))))
                    return str(opt)
            except (TypeError,ValueError):
                pass
            return None
        details.append({
            "question_id":qid,
            "question":q.get("question",q.get("text","")),
            "options":options,
            "correct":ok,
            "submitted":submitted,
            "submitted_text":option_text(submitted),
            "correct_answer":expected,
            "correct_answer_text":option_text(expected),
            "explanation":q.get("explanation",q.get("solution",q.get("answer_explanation","")))
        })
    pct=round(max(score,0)*100/total,2) if total else 0
    result={"test_id":quiz_id,"score":score,"total":total,"percentage":pct,"passed":pct>=float(qz.get("passing_percentage",60)),"correct_count":correct,"wrong_count":wrong,"details":details}
    db.test_attempts.update_one({"_id":attempt["_id"],"user_id":user_id},{"$set":{"user_id":user_id,"test_id":quiz_id,"status":"submitted","answers":answers,"result":result,"submitted_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}},upsert=False)
    cache.delete_prefix(f"quiz_bundle:{user_id}:{quiz_id}")
    cache.delete_prefix(f"results:{user_id}")
    cache.delete_prefix(f"dashboard:{user_id}")
    cache.delete_prefix(f"home:{user_id}")
    cache.delete_prefix(f"learning_summary:{user_id}")
    cache.delete_prefix(f"analytics:{user_id}")
    cache.delete_prefix(f"analytics_summary:{user_id}")
    cache.delete_prefix(f"personalized:{user_id}")
    return result

def _enrich_quiz_results(rows, db):
    rows=list(rows)
    quiz_ids={str(x.get("test_id") or x.get("quiz_id") or "") for x in rows}
    quiz_ids.discard("")
    quizzes={str(q.get("_id")):q for q in db.quizzes.find({"_id":{"$in":list(quiz_ids)}},{"title":1,"name":1,"course_id":1,"category":1})} if quiz_ids else {}
    out=[]
    for row in rows:
        item=clean(row)
        quiz_id=str(item.get("test_id") or item.get("quiz_id") or "")
        qz=quizzes.get(quiz_id)
        if qz:
            item["quiz_title"]=qz.get("title") or qz.get("name") or "Quiz"
            item["course_id"]=qz.get("course_id")
            item["category"]=qz.get("category")
        result=item.get("result") or {}
        if isinstance(result,dict):
            item.setdefault("percentage",result.get("percentage",0))
            item.setdefault("correct_count",result.get("correct_count",0))
            item.setdefault("wrong_count",result.get("wrong_count",0))
            item.setdefault("passed",result.get("passed",False))
            item.setdefault("details",result.get("details",[]))
        out.append(item)
    return out

@router.get("/quizzes/{quiz_id}/results")
def quiz_results(quiz_id: str,user=Depends(current_user)):
    db=get_db()
    rows=list(db.test_attempts.find({"user_id":uid(user),"test_id":quiz_id,"status":"submitted"}).sort("submitted_at",-1))
    return _enrich_quiz_results(rows,db)

@router.get("/results")
def results(user=Depends(current_user)):
    user_id = uid(user); key = f"results:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    db=get_db()
    rows=list(db.test_attempts.find({"user_id":user_id,"status":"submitted"}).sort("submitted_at",-1))
    result = _enrich_quiz_results(rows,db)
    cache.set(key, result, TTL_RESULTS)
    return result

# Questions discovery for learning (not answers)
@router.get("/questions")
def questions(course_id: str|None=None,module_id: str|None=None,topic_id: str|None=None,difficulty: str|None=None,limit:int=Query(100,ge=1,le=500)):
    q={"is_published":True}
    if course_id: q["course_id"]=course_id
    if module_id or topic_id: q["topic_id"]=module_id or topic_id
    if difficulty: q["difficulty"]=difficulty.lower()
    return [clean(x,hide_answers=True) for x in get_db().questions.find(q).limit(limit)]

# Notes
@router.get("/notes")
def notes(user=Depends(current_user)):
    user_id = uid(user); key = f"notes:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().notes.find({"user_id":user_id}).sort("created_at",-1)]
    cache.set(key, result, TTL_NOTES)
    return result

@router.post("/notes")
def add_note(data:dict,user=Depends(current_user)):
    if not data.get("content"): raise HTTPException(422,"Note content is required")
    d={"_id":uuid.uuid4().hex,"user_id":uid(user),"content":data["content"],"lesson_id":data.get("lesson_id"),"course_id":data.get("course_id"),"created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    get_db().notes.insert_one(d); cache.delete_prefix(f"notes:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}"); return clean(d)

@router.put("/notes/{note_id}")
def update_note(note_id:str,data:dict,user=Depends(current_user)):
    x=find_by_id("notes",note_id)
    if not x or x.get("user_id")!=uid(user): raise HTTPException(404,"Note not found")
    d=dict(data); d.pop("_id",None); d["updated_at"]=datetime.now(timezone.utc)
    get_db().notes.update_one({"_id":x["_id"]},{"$set":d}); cache.delete_prefix(f"notes:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}"); return clean(get_db().notes.find_one({"_id":x["_id"]}))

@router.delete("/notes/{note_id}")
def delete_note(note_id:str,user=Depends(current_user)):
    x=find_by_id("notes",note_id)
    if not x or x.get("user_id")!=uid(user): raise HTTPException(404,"Note not found")
    get_db().notes.delete_one({"_id":x["_id"]}); cache.delete_prefix(f"notes:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}"); return {"message":"Note deleted"}
