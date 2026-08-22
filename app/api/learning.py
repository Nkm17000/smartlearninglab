from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_user
from app.db.mongo import get_db

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
    """Return the student dashboard view model used by the modern FE.

    The endpoint intentionally keeps presentation metrics derived from the
    existing learning collections so the frontend does not need to invent
    progress, streaks or weekly goals.
    """
    db = get_db(); user_id = uid(user)
    progress = list(db.progress.find({"user_id": user_id}))
    completed_progress = [p for p in progress if p.get("completed")]
    attempts = list(db.test_attempts.find({"user_id": user_id, "status": "submitted"}).sort("submitted_at", -1))
    avg = round(sum(float(a.get("result", {}).get("percentage", 0)) for a in attempts) / len(attempts), 2) if attempts else 0

    enrollments = list(db.enrollments.find({"user_id": user_id, "status": "active"}).sort("updated_at", -1).limit(10))
    enrolled_courses = []
    continue_learning = None

    for e in enrollments:
        course_id = str(e.get("course_id", ""))
        c = db.courses.find_one({"_id": e.get("course_id")}) or db.courses.find_one({"_id": course_id})
        if not c:
            continue

        total = db.lessons.count_documents({"course_id": course_id, "is_published": True})
        course_done = db.progress.count_documents({"user_id": user_id, "course_id": course_id, "completed": True})
        percentage = round(course_done * 100 / total, 2) if total else 0
        item = clean(c)
        item["progress_percentage"] = percentage
        item["completed_lessons"] = course_done
        item["total_lessons"] = total
        enrolled_courses.append(item)

        if continue_learning is None and total and course_done < total:
            done_ids = {str(x.get("lesson_id")) for x in completed_progress if str(x.get("course_id")) == course_id}
            lesson_query = {"course_id": course_id, "is_published": True}
            candidate_lessons = list(db.lessons.find(lesson_query).sort("order", 1).limit(100))
            next_lesson = next((x for x in candidate_lessons if str(x.get("_id")) not in done_ids), None)
            if next_lesson:
                continue_learning = {
                    "course_id": course_id,
                    "course_title": c.get("name") or c.get("title") or "Course",
                    "lesson_id": str(next_lesson.get("_id")),
                    "lesson_title": next_lesson.get("title") or next_lesson.get("name") or "Next lesson",
                    "progress_percentage": percentage,
                }

    # Weekly goal = completed lessons whose activity timestamp falls in the
    # current calendar week (Monday-Sunday). The target is deliberately small
    # and visible; it can later be made configurable per learner.
    today = datetime.now(timezone.utc).date()
    week_start = today - __import__('datetime').timedelta(days=today.weekday())
    weekly_completed = 0
    for p in completed_progress:
        raw = p.get("completed_at") or p.get("updated_at") or p.get("created_at")
        try:
            if raw:
                d = raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
                if d >= week_start:
                    weekly_completed += 1
        except Exception:
            continue
    weekly_target = 5
    weekly_percentage = min(100, round(weekly_completed * 100 / weekly_target)) if weekly_target else 0

    # Same lightweight XP model used by the growth/analytics endpoint.
    passed = sum(1 for a in attempts if a.get("result", {}).get("passed"))
    completed_courses = 0
    for item in enrolled_courses:
        if item.get("total_lessons") and item.get("completed_lessons", 0) >= item.get("total_lessons"):
            completed_courses += 1
    xp = len(completed_progress) * 10 + passed * 50 + len(attempts) * 5 + completed_courses * 100

    # Keep the dashboard self-contained instead of making the FE depend on a
    # second analytics request.
    activity_dates = set()
    for collection in ("progress", "test_attempts", "enrollments", "notes", "bookmarks", "course_reviews"):
        for row in db[collection].find({"user_id": user_id}, {"created_at": 1, "updated_at": 1, "submitted_at": 1, "completed_at": 1}):
            for key in ("created_at", "updated_at", "submitted_at", "completed_at"):
                raw = row.get(key)
                if not raw:
                    continue
                try:
                    d = raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
                    activity_dates.add(d)
                except Exception:
                    pass
    streak = 0
    cursor = today
    while cursor in activity_dates:
        streak += 1
        cursor -= __import__('datetime').timedelta(days=1)

    return {
        "user": {"id": user_id, "name": user.get("name"), "email": user.get("email"), "role": user.get("role")},
        "courses_available": db.courses.count_documents({"is_published": True}),
        "lessons_completed": len(completed_progress),
        "quiz_attempts": len(attempts),
        "quiz_average": avg,
        "xp": xp,
        "streak": {"current": streak},
        "enrolled_courses": enrolled_courses,
        "continue_learning": continue_learning,
        "weekly_goal": {"target": weekly_target, "completed": weekly_completed, "percentage": weekly_percentage},
        "recent_quiz_results": [clean(x) for x in attempts[:5]],
    }

@router.get("/profile")
def profile(user=Depends(current_user)):
    return {"id": uid(user), "name": user.get("name",""), "email": user.get("email",""), "role": user.get("role","student"), "is_active": user.get("is_active",True)}

@router.get("/courses")
def courses(search: str | None = None, category: str | None = None, exam: str | None = None, level: str | None = None, language: str | None = None, free_only: bool = True, user=Depends(current_user)):
    db = get_db()
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

    user_id = uid(user)
    enrolled_ids = {str(x.get("course_id")) for x in db.enrollments.find({"user_id": user_id}, {"course_id": 1})}
    progress_docs = list(db.progress.find({"user_id": user_id}, {"course_id": 1, "lesson_id": 1, "completed": 1}))
    completed_by_course = {}
    completed_lesson_ids = {str(x.get("lesson_id")) for x in progress_docs if x.get("completed")}

    items = []
    for course in db.courses.find(q).sort([("featured", -1), ("created_at", -1)]):
        course_id = str(course.get("_id"))
        total_lessons = db.lessons.count_documents({"course_id": course_id, "is_published": True})
        completed = db.progress.count_documents({"user_id": user_id, "course_id": course_id, "completed": True})
        quiz_count = db.quizzes.count_documents({"course_id": course_id, "is_published": True})
        resource_count = db.course_resources.count_documents({"course_id": course_id})
        item = clean(course)
        item.update({
            "is_enrolled": course_id in enrolled_ids,
            "lesson_count": total_lessons,
            "quiz_count": quiz_count,
            "pdf_count": resource_count,
            "progress_percentage": round(completed * 100 / total_lessons, 2) if total_lessons else 0,
        })
        items.append(item)
    return items

@router.get("/catalog/categories")
def catalog_categories(user=Depends(current_user)):
    db=get_db()
    cats=[x for x in db.courses.distinct("category") if x]
    exams=[x for x in db.courses.distinct("exam") if x]
    levels=[x for x in db.courses.distinct("level") if x]
    return {"categories":sorted(cats),"exams":sorted(exams),"levels":sorted(levels)}

@router.get("/catalog/featured")
def catalog_featured(limit:int=Query(8,ge=1,le=30),user=Depends(current_user)):
    db=get_db()
    courses=[clean(x) for x in db.courses.find({"is_published":True}).sort([("featured",-1),("created_at",-1)]).limit(limit)]
    quizzes=[clean(x) for x in db.quizzes.find({"is_published":True}).sort([("featured",-1),("created_at",-1)]).limit(limit)]
    return {"courses":courses,"quizzes":quizzes}

@router.get("/courses/{course_id}/overview")
def course_overview(course_id:str,user=Depends(current_user)):
    c=published("courses",course_id); db=get_db()
    modules=[clean(x) for x in db.topics.find({"course_id":course_id,"is_published":True}).sort("order",1)]
    topic_ids=[str(x.get("_id")) for x in modules]
    lessons=[clean(x) for x in db.lessons.find({"course_id":course_id,"topic_id":{"$in":topic_ids},"is_published":True}).sort([("topic_id",1),("order",1)])]
    quizzes=[clean(x) for x in db.quizzes.find({"course_id":course_id,"is_published":True}).sort("created_at",-1)]
    topic_names = {str(x.get("_id")): (x.get("title") or x.get("name") or "Topic") for x in modules}
    for lesson in lessons:
        lesson_id=str(lesson.get("_id"))
        lesson["topic_title"] = topic_names.get(str(lesson.get("topic_id")), "Topic")
        lesson["resources"]=clean(list(db.lesson_resources.find({"lesson_id":lesson_id}).sort("order",1)))
    course_out = clean(c)
    course_out["resources"] = clean(list(db.course_resources.find({"course_id":course_id}).sort("order",1)))
    return {"course":course_out,"modules":modules,"lessons":lessons,"quizzes":quizzes}

@router.get("/courses/{course_id}")
def course(course_id: str, user=Depends(current_user)):
    c = published("courses", course_id)
    out = clean(c)
    out["resources"] = clean(list(get_db().course_resources.find({"course_id":course_id}).sort("order",1)))
    return out

@router.get("/courses/{course_id}/modules")
def course_modules(course_id: str, user=Depends(current_user)):
    published("courses", course_id)
    return [clean(x) for x in get_db().topics.find({"course_id":course_id,"is_published":True}).sort("order",1)]

@router.get("/modules/{module_id}")
def module(module_id: str, user=Depends(current_user)):
    return clean(published("topics", module_id))

@router.get("/modules/{module_id}/lessons")
def module_lessons(module_id: str, user=Depends(current_user)):
    published("topics", module_id)
    return [clean(x) for x in get_db().lessons.find({"topic_id":module_id,"is_published":True}).sort("order",1)]

@router.get("/lessons")
def lessons(course_id: str | None=None, module_id: str | None=None, user=Depends(current_user)):
    q={"is_published":True}
    if course_id: q["course_id"]=course_id
    if module_id: q["topic_id"]=module_id
    return [clean(x) for x in get_db().lessons.find(q).sort("order",1)]

@router.get("/lessons/{lesson_id}")
def lesson(lesson_id: str, user=Depends(current_user)):
    l = published("lessons", lesson_id)
    db = get_db()
    out = clean(l)
    topic = find_by_id("topics", str(l.get("topic_id", ""))) if l.get("topic_id") else None
    out["topic_title"] = (topic.get("title") or topic.get("name")) if topic else "Topic"
    out["resources"] = clean(list(db.lesson_resources.find({"lesson_id":lesson_id}).sort("order",1)))
    return out

@router.post("/courses/{course_id}/enroll")
def enroll(course_id: str, user=Depends(current_user)):
    published("courses", course_id)
    db=get_db(); user_id=uid(user)
    existing=db.enrollments.find_one({"user_id":user_id,"course_id":course_id})
    if existing: return clean(existing)
    d={"_id":uuid.uuid4().hex,"user_id":user_id,"course_id":course_id,"status":"active","created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    db.enrollments.insert_one(d)
    db.courses.update_one({"_id": c_id}, {"$inc": {"students_count": 1}}) if (c_id := course_id) else None
    db.notifications.insert_one({"_id": uuid.uuid4().hex, "user_id": user_id, "title": "Course enrolled", "message": f"You enrolled in {course_id}.", "read": False, "created_at": datetime.now(timezone.utc)})
    return clean(d)

@router.get("/enrollments")
def enrollments(user=Depends(current_user)):
    return [clean(x) for x in get_db().enrollments.find({"user_id":uid(user)}).sort("created_at",-1)]

@router.get("/progress")
def progress(user=Depends(current_user)):
    return [clean(x) for x in get_db().progress.find({"user_id":uid(user)}).sort("updated_at",-1)]

@router.get("/courses/{course_id}/progress")
def course_progress(course_id: str, user=Depends(current_user)):
    published("courses",course_id); db=get_db(); user_id=uid(user)
    topic_ids=[str(x.get("_id")) for x in db.topics.find({"course_id":course_id,"is_published":True},{"_id":1})]
    total=db.lessons.count_documents({"course_id":course_id,"topic_id":{"$in":topic_ids},"is_published":True})
    done=db.progress.count_documents({"user_id":user_id,"course_id":course_id,"completed":True,"lesson_id":{"$in":[str(x.get("_id")) for x in db.lessons.find({"course_id":course_id,"topic_id":{"$in":topic_ids},"is_published":True},{"_id":1})]}})
    return {"course_id":course_id,"total_lessons":total,"completed_lessons":done,"percentage":round(done*100/total,2) if total else 0}

@router.post("/progress")
def save_progress(data: dict, user=Depends(current_user)):
    course_id=data.get("course_id"); lesson_id=data.get("lesson_id")
    if not course_id or not lesson_id: raise HTTPException(422,"course_id and lesson_id are required")
    d=dict(data); d.update({"_id":uuid.uuid4().hex,"user_id":uid(user),"updated_at":datetime.now(timezone.utc)})
    get_db().progress.update_one({"user_id":uid(user),"lesson_id":lesson_id},{"$set":d},upsert=True)
    return clean(get_db().progress.find_one({"user_id":uid(user),"lesson_id":lesson_id}))

@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str, user=Depends(current_user)):
    l=published("lessons",lesson_id); db=get_db()
    d={"_id":uuid.uuid4().hex,"user_id":uid(user),"course_id":l.get("course_id"),"lesson_id":lesson_id,"completed":True,"completed_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    db.progress.update_one({"user_id":uid(user),"lesson_id":lesson_id},{"$set":d},upsert=True)
    db.notifications.insert_one({"_id": uuid.uuid4().hex, "user_id": uid(user), "title": "Lesson completed", "message": "Great job! You completed a lesson.", "read": False, "created_at": datetime.now(timezone.utc)})
    return clean(d)

# Quiz discovery and attempt
@router.get("/quizzes")
def quizzes(course_id: str|None=None, module_id: str|None=None, user=Depends(current_user)):
    q={"is_published":True}
    if course_id: q["course_id"]=course_id
    if module_id: q["module_id"]=module_id
    items=[]
    db=get_db()
    for x in db.quizzes.find(q).sort("created_at",-1):
        # Quiz publication is controlled by the quiz itself. This keeps the
        # student Quizzes page usable for bulk-created/legacy quizzes whose
        # parent course was created as draft before the quiz was published.
        item=clean(x)
        ids=list(x.get("question_ids",[]) or [])
        item["question_count"]=len(ids)
        item["is_ready"]=len(ids)>0
        items.append(item)
    return items

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id: str, user=Depends(current_user)):
    return clean(published("quizzes",quiz_id))

@router.get("/quizzes/{quiz_id}/questions")
def quiz_questions(quiz_id: str, user=Depends(current_user)):
    qz=published("quizzes",quiz_id)
    ids=[str(x) for x in qz.get("question_ids",[])]
    # The quiz itself is the publication boundary.  Bulk-imported questions
    # may still be draft records until the admin publishes the quiz. Once the
    # quiz is published, return its attached questions in quiz order while
    # still hiding the answer/explanation from the student.
    allq=list(get_db().questions.find({}))
    by={str(x["_id"]):x for x in allq}
    return [clean(by[i],hide_answers=True) for i in ids if i in by]

@router.post("/quizzes/{quiz_id}/start")
def start_quiz(quiz_id: str, user=Depends(current_user)):
    qz=published("quizzes",quiz_id); db=get_db(); user_id=uid(user)
    attempts=db.test_attempts.count_documents({"user_id":user_id,"test_id":quiz_id})
    if attempts>=int(qz.get("max_attempts",3)): raise HTTPException(400,"Maximum attempts reached")
    a={"_id":uuid.uuid4().hex,"user_id":user_id,"test_id":quiz_id,"status":"started","started_at":datetime.now(timezone.utc)}
    db.test_attempts.insert_one(a)
    return {"attempt_id":a["_id"],"quiz_id":quiz_id,"duration_minutes":qz.get("duration_minutes",15)}

@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: str, data: dict, user=Depends(current_user)):
    qz=published("quizzes",quiz_id); db=get_db(); user_id=uid(user)
    answers=data.get("answers",{}) or {}
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
    attempt_id=data.get("attempt_id")
    query={"_id":attempt_id,"user_id":user_id} if attempt_id else {"user_id":user_id,"test_id":quiz_id,"status":"started"}
    db.test_attempts.update_one(query,{"$set":{"user_id":user_id,"test_id":quiz_id,"status":"submitted","result":result,"submitted_at":datetime.now(timezone.utc)}},upsert=False)
    return result

def _enrich_quiz_result(row, db):
    item=clean(row)
    quiz_id=str(item.get("test_id") or item.get("quiz_id") or "")
    qz=db.quizzes.find_one({"_id":quiz_id})
    if not qz:
        try:
            from bson import ObjectId
            if ObjectId.is_valid(quiz_id):
                qz=db.quizzes.find_one({"_id":ObjectId(quiz_id)})
        except Exception:
            pass
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
    return item

@router.get("/quizzes/{quiz_id}/results")
def quiz_results(quiz_id: str,user=Depends(current_user)):
    db=get_db()
    return [_enrich_quiz_result(x,db) for x in db.test_attempts.find({"user_id":uid(user),"test_id":quiz_id,"status":"submitted"}).sort("submitted_at",-1)]

@router.get("/results")
def results(user=Depends(current_user)):
    db=get_db()
    return [_enrich_quiz_result(x,db) for x in db.test_attempts.find({"user_id":uid(user),"status":"submitted"}).sort("submitted_at",-1)]

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
    return [clean(x) for x in get_db().notes.find({"user_id":uid(user)}).sort("created_at",-1)]

@router.post("/notes")
def add_note(data:dict,user=Depends(current_user)):
    if not data.get("content"): raise HTTPException(422,"Note content is required")
    d={"_id":uuid.uuid4().hex,"user_id":uid(user),"content":data["content"],"lesson_id":data.get("lesson_id"),"course_id":data.get("course_id"),"created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc)}
    get_db().notes.insert_one(d); return clean(d)

@router.put("/notes/{note_id}")
def update_note(note_id:str,data:dict,user=Depends(current_user)):
    x=find_by_id("notes",note_id)
    if not x or x.get("user_id")!=uid(user): raise HTTPException(404,"Note not found")
    d=dict(data); d.pop("_id",None); d["updated_at"]=datetime.now(timezone.utc)
    get_db().notes.update_one({"_id":x["_id"]},{"$set":d}); return clean(get_db().notes.find_one({"_id":x["_id"]}))

@router.delete("/notes/{note_id}")
def delete_note(note_id:str,user=Depends(current_user)):
    x=find_by_id("notes",note_id)
    if not x or x.get("user_id")!=uid(user): raise HTTPException(404,"Note not found")
    get_db().notes.delete_one({"_id":x["_id"]}); return {"message":"Note deleted"}
