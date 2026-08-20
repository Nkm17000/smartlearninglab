from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongo import get_db
from app.core.security import current_user
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1", tags=["Learning"])

def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k,v in x.items() if k not in {"password_hash"}}
    if isinstance(x, list): return [clean(v) for v in x]
    if hasattr(x, "isoformat"): return x.isoformat()
    return x

def find_many(collection, query=None, limit=200):
    return [clean(x) for x in get_db()[collection].find(query or {}).limit(limit)]

@router.get("/exams")
def exams(): return find_many("exams")
@router.get("/exams/{item_id}")
def exam(item_id: str):
    x=get_db().exams.find_one({"_id":item_id});
    if not x: raise HTTPException(404,"Exam not found")
    return clean(x)
@router.get("/subjects")
def subjects(exam_id: str|None=None): return find_many("subjects", {"exam_id":exam_id} if exam_id else {})
@router.get("/topics")
def topics(subject_id: str|None=None): return find_many("topics", {"subject_id":subject_id} if subject_id else {})
@router.get("/courses")
def courses(subject_id: str|None=None, topic_id: str|None=None):
    q={};
    if subject_id:q["subject_id"]=subject_id
    if topic_id:q["topic_id"]=topic_id
    return find_many("courses",q)
@router.get("/lessons")
def lessons(course_id: str|None=None): return find_many("lessons", {"course_id":course_id} if course_id else {})
@router.get("/questions")
def questions(topic_id: str|None=None, subject_id: str|None=None, limit: int=Query(20, ge=1, le=200)):
    q={};
    if topic_id:q["topic_id"]=topic_id
    if subject_id:q["subject_id"]=subject_id
    return find_many("questions",q,limit)
@router.get("/mock-tests")
def mock_tests(): return find_many("mock_tests")
@router.get("/current-affairs")
def current_affairs(): return find_many("current_affairs")

@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    db=get_db()
    return {"user": {"id":user["_id"],"name":user["name"],"role":user.get("role")}, "courses":db.courses.count_documents({"is_published":True}), "lessons":db.lessons.count_documents({"is_published":True}), "questions":db.questions.count_documents({"is_published":True}), "quizzes":db.quizzes.count_documents({"is_published":True}) + db.mock_tests.count_documents({"is_published":True})}

@router.post("/tests/{test_id}/submit")
def submit_test(test_id: str, payload: dict, user=Depends(current_user)):
    test=get_db().mock_tests.find_one({"_id":test_id}) or get_db().quizzes.find_one({"_id":test_id})
    if not test: raise HTTPException(404,"Test not found")
    answers=payload.get("answers",{})
    ids=[str(x) for x in test.get("question_ids",[])]
    questions=list(get_db().questions.find({"_id":{"$in":ids}}))
    score=0
    for q in questions:
        submitted=answers.get(str(q["_id"]))
        correct=q.get("correct_answer",q.get("answer"))
        if submitted == correct: score += q.get("marks",1)
    total=sum(q.get("marks",1) for q in questions) or len(questions) or 1
    pct=round(score*100/total,2)
    result={"test_id":test_id,"score":score,"total":total,"percentage":pct,"passed":pct>=test.get("passing_percentage",60)}
    get_db().test_attempts.insert_one({"_id":__import__('uuid').uuid4().hex,"user_id":user["_id"],"result":result,"created_at":datetime.now(timezone.utc)})
    return result

@router.post("/progress")
def save_progress(payload: dict, user=Depends(current_user)):
    payload=dict(payload); payload["user_id"]=user["_id"]; payload["updated_at"]=datetime.now(timezone.utc)
    key={"user_id":user["_id"],"course_id":payload.get("course_id"),"lesson_id":payload.get("lesson_id")}
    get_db().progress.update_one(key,{"$set":payload},upsert=True); return payload
@router.get("/progress")
def progress(user=Depends(current_user)): return find_many("progress",{"user_id":user["_id"]})
@router.get("/profile")
def profile(user=Depends(current_user)): return {"id":user["_id"],"name":user["name"],"email":user["email"],"role":user.get("role")}
@router.get("/mistakes")
def mistakes(user=Depends(current_user)): return find_many("mistakes",{"user_id":user["_id"]})
@router.get("/notes")
def notes(user=Depends(current_user)): return find_many("notes",{"user_id":user["_id"]})
@router.post("/notes")
def add_note(data: dict, user=Depends(current_user)):
    d=dict(data); d.update({"_id":__import__('uuid').uuid4().hex,"user_id":user["_id"],"created_at":datetime.now(timezone.utc)}); get_db().notes.insert_one(d); return clean(d)
