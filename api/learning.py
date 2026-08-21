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
    x = find_by_id(collection, item_id)
    if not x: raise HTTPException(404, f"{collection.rstrip('s').capitalize()} not found")
    if x.get("is_published") is False: raise HTTPException(404, "Content not published")
    return x

def uid(user): return str(user["_id"])

@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    progress = list(db.progress.find({"user_id": user_id}))
    attempts = list(db.test_attempts.find({"user_id": user_id, "status": "submitted"}))
    avg = round(sum(float(a.get("result", {}).get("percentage", 0)) for a in attempts)/len(attempts), 2) if attempts else 0
    done = sum(1 for p in progress if p.get("completed"))
    enrollments=list(db.enrollments.find({"user_id":user_id,"status":"active"}).sort("updated_at",-1).limit(6))
    enrolled_courses=[]
    for e in enrollments:
        c=db.courses.find_one({"_id":e.get("course_id")})
        if c:
            course_id=str(e.get("course_id"))
            total=db.lessons.count_documents({"course_id":course_id,"is_published":True})
            done=db.progress.count_documents({"user_id":user_id,"course_id":course_id,"completed":True})
            item=clean(c)
            item["progress_percentage"]=round(done*100/total,2) if total else 0
            item["completed_lessons"]=done
            item["total_lessons"]=total
            enrolled_courses.append(item)
    return {
        "user": {"id": user_id, "name": user.get("name"), "email": user.get("email"), "role": user.get("role")},
        "courses_available": db.courses.count_documents({"is_published": True}),
        "lessons_completed": done,
        "quiz_attempts": len(attempts),
        "quiz_average": avg,
        "enrolled_courses": enrolled_courses,
        "recent_quiz_results": [clean(x) for x in attempts[:5]],
    }

@router.get("/profile")
def profile(user=Depends(current_user)):
    return {"id": uid(user), "name": user.get("name",""), "email": user.get("email",""), "role": user.get("role","student"), "is_active": user.get("is_active",True)}

@router.get("/courses")
def courses(search: str | None = None, category: str | None = None, level: str | None = None, language: str | None = None, free_only: bool = True, user=Depends(current_user)):
    q = {"is_published": True}
    if search:
        q["$or"] = [
            {"name":{"$regex":search,"$options":"i"}},
            {"title":{"$regex":search,"$options":"i"}},
            {"description":{"$regex":search,"$options":"i"}},
            {"exam":{"$regex":search,"$options":"i"}},
            {"tags":{"$regex":search,"$options":"i"}},
        ]
    if category: q["category"] = {"$regex":category,"$options":"i"}
    if level: q["level"] = {"$regex":level,"$options":"i"}
    if language: q["language"] = {"$regex":language,"$options":"i"}
    if free_only: q["$or_free"] = True
    # Mongo cannot use a synthetic key; free courses are the default in this free app.
    if "or_free" in q: q.pop("or_free", None)
    items=[clean(x) for x in get_db().courses.find(q).sort([("featured",-1),("created_at",-1)])]
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
    lessons=[clean(x) for x in db.lessons.find({"course_id":course_id,"is_published":True}).sort("order",1)]
    quizzes=[clean(x) for x in db.quizzes.find({"course_id":course_id,"is_published":True}).sort("created_at",-1)]
    for lesson in lessons:
        lesson_id=str(lesson.get("_id"))
        lesson["resources"]=clean(list(db.lesson_resources.find({"lesson_id":lesson_id}).sort("order",1)))
    return {"course":clean(c),"modules":modules,"lessons":lessons,"quizzes":quizzes}

@router.get("/courses/{course_id}")
def course(course_id: str, user=Depends(current_user)):
    return clean(published("courses", course_id))

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
    return clean(published("lessons", lesson_id))

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
    total=db.lessons.count_documents({"course_id":course_id,"is_published":True})
    done=db.progress.count_documents({"user_id":user_id,"course_id":course_id,"completed":True})
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
    return [clean(x) for x in get_db().quizzes.find(q).sort("created_at",-1)]

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id: str, user=Depends(current_user)):
    return clean(published("quizzes",quiz_id))

@router.get("/quizzes/{quiz_id}/questions")
def quiz_questions(quiz_id: str, user=Depends(current_user)):
    qz=published("quizzes",quiz_id)
    ids=[str(x) for x in qz.get("question_ids",[])]
    found=list(get_db().questions.find({"is_published":True}))
    by={str(x["_id"]):x for x in found}
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
    allq=list(db.questions.find({"is_published":True}))
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
        details.append({"question_id":qid,"correct":ok,"submitted":submitted})
    pct=round(max(score,0)*100/total,2) if total else 0
    result={"test_id":quiz_id,"score":score,"total":total,"percentage":pct,"passed":pct>=float(qz.get("passing_percentage",60)),"correct_count":correct,"wrong_count":wrong,"details":details}
    attempt_id=data.get("attempt_id")
    query={"_id":attempt_id,"user_id":user_id} if attempt_id else {"user_id":user_id,"test_id":quiz_id,"status":"started"}
    db.test_attempts.update_one(query,{"$set":{"user_id":user_id,"test_id":quiz_id,"status":"submitted","result":result,"submitted_at":datetime.now(timezone.utc)}},upsert=False)
    return result

@router.get("/quizzes/{quiz_id}/results")
def quiz_results(quiz_id: str,user=Depends(current_user)):
    return [clean(x) for x in get_db().test_attempts.find({"user_id":uid(user),"test_id":quiz_id,"status":"submitted"}).sort("submitted_at",-1)]

@router.get("/results")
def results(user=Depends(current_user)):
    return [clean(x) for x in get_db().test_attempts.find({"user_id":uid(user),"status":"submitted"}).sort("submitted_at",-1)]

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
