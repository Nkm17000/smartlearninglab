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

def _course_count_map(db, collection, match):
    return {str(x["_id"]): int(x["count"]) for x in db[collection].aggregate([{"$match":match},{"$group":{"_id":"$course_id","count":{"$sum":1}}}]) if x.get("_id") is not None}

def _build_dashboard(db,user):
    user_id=uid(user)
    progress=list(db.progress.find({"user_id":user_id},{"course_id":1,"lesson_id":1,"completed":1,"completed_at":1,"updated_at":1,"created_at":1}))
    completed=[x for x in progress if x.get("completed")]
    attempts=list(db.test_attempts.find({"user_id":user_id,"status":"submitted"},{"test_id":1,"result":1,"submitted_at":1}).sort("submitted_at",-1).limit(50))
    enrollments=list(db.enrollments.find({"user_id":user_id,"status":"active"},{"course_id":1,"updated_at":1}).sort("updated_at",-1).limit(10))
    ids=[str(x.get("course_id")) for x in enrollments if x.get("course_id") is not None]
    courses=list(db.courses.find({"_id":{"$in":ids},"is_published":True},{"name":1,"title":1,"short_description":1,"description":1,"level":1,"category":1,"exam":1,"language":1,"thumbnail":1,"featured":1,"is_free":1,"created_at":1})) if ids else []
    by={str(x.get("_id")):x for x in courses}; lc=_course_count_map(db,"lessons",{"course_id":{"$in":ids},"is_published":True}) if ids else {}; pc=_course_count_map(db,"progress",{"user_id":user_id,"course_id":{"$in":ids},"completed":True}) if ids else {}
    done_by={}
    for x in completed: done_by.setdefault(str(x.get("course_id")),set()).add(str(x.get("lesson_id")))
    nexts={}
    for x in (list(db.lessons.find({"course_id":{"$in":ids},"is_published":True},{"_id":1,"course_id":1,"title":1,"name":1,"order":1}).sort("order",1).limit(200)) if ids else []):
        cid=str(x.get("course_id"));
        if cid not in nexts and str(x.get("_id")) not in done_by.get(cid,set()): nexts[cid]=x
    enrolled=[]; cont=None
    for e in enrollments:
        cid=str(e.get("course_id")); c=by.get(cid)
        if not c: continue
        total=lc.get(cid,0); done=pc.get(cid,0); item=clean(c); item.update({"is_enrolled":True,"lesson_count":total,"completed_lessons":done,"total_lessons":total,"progress_percentage":round(done*100/total,2) if total else 0}); enrolled.append(item)
        if cont is None and cid in nexts:
            x=nexts[cid]; cont={"course_id":cid,"course_title":c.get("name") or c.get("title") or "Course","lesson_id":str(x.get("_id")),"lesson_title":x.get("title") or x.get("name") or "Next lesson","progress_percentage":item["progress_percentage"]}
    today=datetime.now(timezone.utc).date(); week=today-__import__('datetime').timedelta(days=today.weekday()); dates=set(); weekly=0
    for x in completed:
        raw=x.get("completed_at") or x.get("updated_at") or x.get("created_at")
        try:
            d=raw.date() if hasattr(raw,"date") else datetime.fromisoformat(str(raw).replace("Z","+00:00")).date(); dates.add(d); weekly+=d>=week
        except Exception: pass
    for x in attempts:
        raw=x.get("submitted_at")
        try: dates.add(raw.date() if hasattr(raw,"date") else datetime.fromisoformat(str(raw).replace("Z","+00:00")).date())
        except Exception: pass
    streak=0; cur=today
    while cur in dates: streak+=1; cur-=__import__('datetime').timedelta(days=1)
    pct=[float((x.get("result") or {}).get("percentage",0) or 0) for x in attempts]; avg=round(sum(pct)/len(pct),2) if pct else 0; passed=sum(1 for x in attempts if bool((x.get("result") or {}).get("passed"))); completed_courses=sum(1 for x in enrolled if x["total_lessons"] and x["completed_lessons"]>=x["total_lessons"]); xp=len(completed)*10+len(attempts)*5+passed*50+completed_courses*100
    return {"user":{"id":user_id,"name":user.get("name"),"email":user.get("email"),"role":user.get("role")},"courses_available":db.courses.count_documents({"is_published":True}),"lessons_completed":len(completed),"quiz_attempts":len(attempts),"quiz_average":avg,"xp":xp,"streak":{"current":streak},"enrolled_courses":enrolled,"continue_learning":cont,"weekly_goal":{"target":5,"completed":weekly,"percentage":min(100,round(weekly*20))},"recent_quiz_results":[clean(x) for x in attempts[:5]]}

@router.get("/dashboard")
def dashboard(user=Depends(current_user)): return _build_dashboard(get_db(),user)

@router.get("/home")
def home(limit:int=Query(10,ge=1,le=20),user=Depends(current_user)):
    db=get_db(); courses=[clean(x) for x in db.courses.find({"is_published":True},{"name":1,"title":1,"short_description":1,"description":1,"level":1,"category":1,"exam":1,"is_free":1,"thumbnail":1,"featured":1,"created_at":1,"video_count":1,"mock_test_count":1,"pdf_count":1}).sort([("featured",-1),("created_at",-1)]).limit(limit)]; quizzes=[clean(x) for x in db.quizzes.find({"is_published":True},{"title":1,"name":1,"duration_minutes":1,"question_ids":1,"featured":1,"created_at":1}).sort([("featured",-1),("created_at",-1)]).limit(6)]; catalog={"categories":sorted([x for x in db.courses.distinct("category",{"is_published":True}) if x]),"exams":sorted([x for x in db.courses.distinct("exam",{"is_published":True}) if x])}; return {"dashboard":_build_dashboard(db,user),"courses":courses,"quizzes":quizzes,"catalog":catalog}

def _learning_plan(db,user):
    user_id=uid(user); attempts=list(db.test_attempts.find({"user_id":user_id,"status":"submitted"},{"test_id":1,"result":1,"submitted_at":1}).sort("submitted_at",-1).limit(30)); ids=[str(x.get("test_id")) for x in attempts if x.get("test_id")]; qzs=list(db.quizzes.find({"_id":{"$in":ids}},{"title":1,"name":1})) if ids else []; qby={str(x.get("_id")):x for x in qzs}; weak=[]; pcts=[]
    for a in attempts:
        r=a.get("result") or {}; pct=float(r.get("percentage",0) or 0); pcts.append(pct);
        if pct<70: weak.append({"quiz_id":str(a.get("test_id") or ""),"score":pct,"topic":(qby.get(str(a.get("test_id"))) or {}).get("title") or (qby.get(str(a.get("test_id"))) or {}).get("name") or "Quiz review"})
    completed=list(db.progress.find({"user_id":user_id,"completed":True},{"course_id":1,"lesson_id":1,"completed_at":1,"updated_at":1,"created_at":1})); completed_ids={str(x.get("lesson_id")) for x in completed}; enroll=list(db.enrollments.find({"user_id":user_id,"status":"active"},{"course_id":1}).limit(30)); eids=[str(x.get("course_id")) for x in enroll if x.get("course_id") is not None]; lessons=list(db.lessons.find({"is_published":True,"course_id":{"$in":eids}},{"_id":1,"course_id":1,"title":1,"name":1,"description":1,"duration_minutes":1,"order":1}).sort("order",1).limit(60)) if eids else []; overall=round(len(completed_ids)*100/len(lessons),2) if lessons else 0; today=datetime.now(timezone.utc).date(); week=today-__import__('datetime').timedelta(days=today.weekday()); weekly=0; today_done=0; dates=set()
    for x in completed:
        raw=x.get("completed_at") or x.get("updated_at") or x.get("created_at")
        try:
            d=raw.date() if hasattr(raw,"date") else datetime.fromisoformat(str(raw).replace("Z","+00:00")).date(); dates.add(d); weekly+=d>=week; today_done+=d==today
        except Exception: pass
    for a in attempts:
        raw=a.get("submitted_at")
        try: dates.add(raw.date() if hasattr(raw,"date") else datetime.fromisoformat(str(raw).replace("Z","+00:00")).date())
        except Exception: pass
    streak=0; cur=today
    while cur in dates: streak+=1; cur-=__import__('datetime').timedelta(days=1)
    passed=sum(1 for a in attempts if bool((a.get("result") or {}).get("passed"))); avg=round(sum(pcts)/len(pcts),2) if pcts else 0; flash=db.flashcard_reviews.count_documents({"user_id":user_id}); lc=_course_count_map(db,"lessons",{"course_id":{"$in":eids},"is_published":True}) if eids else {}; pc=_course_count_map(db,"progress",{"user_id":user_id,"course_id":{"$in":eids},"completed":True}) if eids else {}; cc=sum(1 for cid in eids if lc.get(cid,0)>0 and pc.get(cid,0)>=lc.get(cid,0)); nexts=[]
    for l in lessons:
        if str(l.get("_id")) in completed_ids: continue
        x=clean(l); x.update({"type":"lesson","course_id":str(l.get("course_id")),"progress_percentage":0,"duration_minutes":int(l.get("duration_minutes",25) or 25),"badge":"Weak Area" if weak and not nexts else ("Recommended" if len(nexts)==1 else "Review")}); nexts.append(x)
        if len(nexts)>=6: break
    xp=len(completed)*10+len(attempts)*5+passed*50; return {"summary":"Personalized recommendations based on your progress and recent assessment performance.","weak_areas":weak[:6],"next_steps":nexts,"daily_goal_minutes":20,"today_minutes":today_done*10,"weekly_goal_lessons":5,"weekly_completed_lessons":weekly,"overall_progress":overall,"courses_completed":cc,"courses_total":len(enroll),"quizzes_completed":len(attempts),"quizzes_passed":passed,"flashcards_reviewed":flash,"accuracy":avg,"study_hours":f"{(len(completed)*25)//60}h {(len(completed)*25)%60}m","streak_days":streak,"xp":xp}

@router.get("/learning/summary")
def learning_summary(user=Depends(current_user)):
    db=get_db(); uid_=uid(user); raw=list(db.courses.find({"is_published":True},{"name":1,"title":1,"short_description":1,"description":1,"level":1,"category":1,"exam":1,"is_free":1,"thumbnail":1,"featured":1,"created_at":1}).sort([("featured",-1),("created_at",-1)]).limit(100)); ids=[str(x.get("_id")) for x in raw]; lc=_course_count_map(db,"lessons",{"course_id":{"$in":ids},"is_published":True}) if ids else {}; pc=_course_count_map(db,"progress",{"user_id":uid_,"course_id":{"$in":ids},"completed":True}) if ids else {}; courses=[]
    for c in raw:
        x=clean(c); cid=str(c.get("_id")); total=lc.get(cid,0); done=pc.get(cid,0); x.update({"lesson_count":total,"progress_percentage":round(done*100/total,2) if total else 0}); courses.append(x)
    progress=[clean(x) for x in db.progress.find({"user_id":uid_},{"course_id":1,"lesson_id":1,"completed":1,"completed_at":1,"updated_at":1}).sort("updated_at",-1).limit(500)]; results=_enrich_quiz_results(list(db.test_attempts.find({"user_id":uid_,"status":"submitted"}).sort("submitted_at",-1).limit(100)),db); return {"courses":courses,"progress":progress,"results":results,"plan":_learning_plan(db,user)}

@router.get("/profile")
def profile(user=Depends(current_user)):
    return {"id": uid(user), "name": user.get("name",""), "email": user.get("email",""), "role": user.get("role","student"), "is_active": user.get("is_active",True)}

@router.get("/courses")
def courses(search:str|None=None,category:str|None=None,exam:str|None=None,level:str|None=None,language:str|None=None,free_only:bool=False,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=50),user=Depends(current_user)):
    db=get_db(); uid_=uid(user); q={"is_published":True}
    if search:
        z=re.escape(search.strip()); q["$or"]=[{"name":{"$regex":z,"$options":"i"}},{"title":{"$regex":z,"$options":"i"}},{"description":{"$regex":z,"$options":"i"}},{"exam":{"$regex":z,"$options":"i"}},{"tags":{"$regex":z,"$options":"i"}}]
    if category:q["category"]=category
    if exam:q["exam"]=exam
    if level:q["level"]=level
    if language:q["language"]=language
    if free_only:q["is_free"]=True
    raw=list(db.courses.find(q,{"name":1,"title":1,"short_description":1,"description":1,"level":1,"category":1,"exam":1,"language":1,"is_free":1,"thumbnail":1,"featured":1,"created_at":1,"video_count":1,"mock_test_count":1,"pdf_count":1}).sort([("featured",-1),("created_at",-1)]).skip((page-1)*limit).limit(limit)); ids=[str(x.get("_id")) for x in raw]; enrolled={str(x.get("course_id")) for x in db.enrollments.find({"user_id":uid_},{"course_id":1})}; lc=_course_count_map(db,"lessons",{"course_id":{"$in":ids},"is_published":True}) if ids else {}; qc=_course_count_map(db,"quizzes",{"course_id":{"$in":ids},"is_published":True}) if ids else {}; rc=_course_count_map(db,"course_resources",{"course_id":{"$in":ids}}) if ids else {}; pc=_course_count_map(db,"progress",{"user_id":uid_,"course_id":{"$in":ids},"completed":True}) if ids else {}; items=[]
    for c in raw:
        cid=str(c.get("_id")); total=lc.get(cid,0); done=pc.get(cid,0); item=clean(c); item.update({"is_enrolled":cid in enrolled,"lesson_count":total,"quiz_count":qc.get(cid,0),"pdf_count":rc.get(cid,0),"progress_percentage":round(done*100/total,2) if total else 0}); items.append(item)
    return {"items":items,"page":page,"limit":limit,"has_more":len(raw)==limit}

@router.get("/courses/{course_id}/overview")
def course_overview(course_id:str,user=Depends(current_user)):
    db=get_db(); c=published("courses",course_id); user_id=uid(user); modules=[clean(x) for x in db.topics.find({"course_id":course_id,"is_published":True}).sort("order",1)]; tids=[str(x.get("_id")) for x in modules]; raw=list(db.lessons.find({"course_id":course_id,"topic_id":{"$in":tids},"is_published":True},{"title":1,"name":1,"description":1,"topic_id":1,"order":1,"duration_minutes":1,"content":1}).sort([("topic_id",1),("order",1)])); lids=[str(x.get("_id")) for x in raw]; rr=list(db.lesson_resources.find({"lesson_id":{"$in":lids}},{"lesson_id":1,"title":1,"url":1,"type":1,"order":1,"duration_seconds":1}).sort("order",1)) if lids else []; rb={}
    for x in rr: rb.setdefault(str(x.get("lesson_id")),[]).append(clean(x))
    names={str(x.get("_id")):(x.get("title") or x.get("name") or "Topic") for x in modules}; done_rows=list(db.progress.find({"user_id":user_id,"course_id":course_id,"completed":True},{"lesson_id":1})); done_ids={str(x.get("lesson_id")) for x in done_rows}; lessons=[]
    for x in raw:
        item=clean(x); item["topic_title"]=names.get(str(x.get("topic_id")),"Topic"); item["resources"]=rb.get(str(x.get("_id")),[]); item["completed"]=str(x.get("_id")) in done_ids; lessons.append(item)
    co=clean(c); co["resources"]=[clean(x) for x in db.course_resources.find({"course_id":course_id},{"title":1,"url":1,"type":1,"order":1}).sort("order",1)]; quizzes=[clean(x) for x in db.quizzes.find({"course_id":course_id,"is_published":True},{"title":1,"name":1,"duration_minutes":1,"question_ids":1,"passing_percentage":1,"created_at":1}).sort("created_at",-1)]; reviews=[clean(x) for x in db.course_reviews.find({"course_id":course_id},{"user_id":1,"user_name":1,"rating":1,"review":1,"created_at":1}).sort("created_at",-1).limit(50)]; bookmarked=bool(db.bookmarks.find_one({"user_id":user_id,"item_type":"course","item_id":course_id},{"_id":1})); total=len(lessons); done=len(done_ids); return {"course":co,"modules":modules,"lessons":lessons,"quizzes":quizzes,"reviews":reviews,"bookmarked":bookmarked,"progress":{"course_id":course_id,"total_lessons":total,"completed_lessons":done,"percentage":round(done*100/total,2) if total else 0}}

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
def course_progress(course_id:str,user=Depends(current_user)):
    published("courses",course_id); db=get_db(); user_id=uid(user); total=db.lessons.count_documents({"course_id":course_id,"is_published":True}); done=db.progress.count_documents({"user_id":user_id,"course_id":course_id,"completed":True}); return {"course_id":course_id,"total_lessons":total,"completed_lessons":done,"percentage":round(done*100/total,2) if total else 0}

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
def quiz_questions(quiz_id:str,user=Depends(current_user)):
    qz=published("quizzes",quiz_id); ids=[str(x) for x in qz.get("question_ids",[])];
    if not ids:return []
    docs=list(get_db().questions.find({"_id":{"$in":ids}})); by={str(x.get("_id")):x for x in docs}; return [clean(by[i],hide_answers=True) for i in ids if i in by]

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

def _enrich_quiz_results(rows,db):
    items=[clean(x) for x in rows]; ids={str(x.get("test_id") or x.get("quiz_id") or "") for x in items}; ids.discard(""); qs=list(db.quizzes.find({"_id":{"$in":list(ids)}},{"title":1,"name":1,"course_id":1,"category":1})) if ids else []; by={str(x.get("_id")):x for x in qs}
    for item in items:
        q=by.get(str(item.get("test_id") or item.get("quiz_id") or ""));
        if q: item.update({"quiz_title":q.get("title") or q.get("name") or "Quiz","course_id":q.get("course_id"),"category":q.get("category")})
        r=item.get("result") or {}
        if isinstance(r,dict): item.setdefault("percentage",r.get("percentage",0)); item.setdefault("correct_count",r.get("correct_count",0)); item.setdefault("wrong_count",r.get("wrong_count",0)); item.setdefault("passed",r.get("passed",False)); item.setdefault("details",r.get("details",[]))
    return items

@router.get("/quizzes/{quiz_id}/results")
def quiz_results(quiz_id:str,user=Depends(current_user)):
    db=get_db(); return _enrich_quiz_results(list(db.test_attempts.find({"user_id":uid(user),"test_id":quiz_id,"status":"submitted"}).sort("submitted_at",-1).limit(50)),db)

@router.get("/results")
def results(user=Depends(current_user)):
    db=get_db(); return _enrich_quiz_results(list(db.test_attempts.find({"user_id":uid(user),"status":"submitted"}).sort("submitted_at",-1).limit(100)),db)

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
