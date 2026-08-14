from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.dependencies import get_current_user
from app.database import collection
from app.repositories.progress_repository import ProgressRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.content_compat import find_questions
from app.utils import clean_doc

router=APIRouter()
progress_repo=ProgressRepository()
bookmark_repo=BookmarkRepository()
attempt_repo=QuizAttemptRepository()

@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"status":"success","data":user}

@router.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    uid=user["_id"]
    progress=progress_repo.list_for_user(uid)
    attempts=attempt_repo.list_for_user(uid)
    values=[int(x.get("progress_percent",x.get("progress",0)) or 0) for x in progress]
    avg=round(sum(values)/len(values)) if values else 0
    return {"status":"success","data":{
        "overall_progress":avg,"courses_enrolled":len(set(str(x.get("course_id",x.get("courseId",""))) for x in progress if x.get("course_id") or x.get("courseId"))),
        "quizzes_completed":len(attempts),"lessons_completed":sum(1 for x in progress if x.get("completed") is True or x.get("completed")==1)
    }}

class ProgressIn(BaseModel):
    course_id:str
    lesson_id:str
    progress_percent:int=Field(0,ge=0,le=100)
    completed:bool=False

@router.get("/progress")
def progress(user=Depends(get_current_user)):
    return {"status":"success","data":progress_repo.list_for_user(user["_id"])}

@router.post("/progress")
def set_progress(x:ProgressIn,user=Depends(get_current_user)):
    return {"status":"success","data":progress_repo.upsert(user["_id"],x.model_dump())}

class BookmarkIn(BaseModel):
    lesson_id:str
    note:str=""

@router.get("/bookmarks")
def bookmarks(user=Depends(get_current_user)):
    return {"status":"success","data":bookmark_repo.list_for_user(user["_id"])}

@router.post("/bookmarks")
def add_bookmark(x:BookmarkIn,user=Depends(get_current_user)):
    return {"status":"success","data":bookmark_repo.upsert(user["_id"],x.lesson_id,x.note)}

@router.delete("/bookmarks/{lesson_id}")
def remove_bookmark(lesson_id,user=Depends(get_current_user)):
    bookmark_repo.delete(user["_id"],lesson_id)
    return {"status":"success","message":"Bookmark removed"}

class QuizSubmit(BaseModel):
    answers:dict[str,int]

@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id:str,x:QuizSubmit,user=Depends(get_current_user)):
    questions=find_questions(quiz_id)
    if not questions: raise HTTPException(404,"Quiz questions not found")
    correct=0
    for q in questions:
        expected=q.get("answer",q.get("correct_answer"))
        selected=x.answers.get(str(q["_id"]),x.answers.get(q.get("id","")))
        if selected is not None and int(selected)==int(expected):
            correct+=1
    total=len(questions); score=round(correct*100/total)
    saved=attempt_repo.insert({"user_id":user["_id"],"quiz_id":quiz_id,"score":score,
                               "correct":correct,"total":total})
    return {"status":"success","data":{"score":score,"correct":correct,"total":total,"passed":score>=60,"attempt":saved}}

@router.get("/achievements")
def achievements(user=Depends(get_current_user)):
    return {"status":"success","data":[clean_doc(x) for x in collection("achievements").find({"user_id":user["_id"]}).limit(100)]}

@router.get("/notifications")
def notifications(user=Depends(get_current_user)):
    return {"status":"success","data":[clean_doc(x) for x in collection("notifications").find({"user_id":user["_id"]}).sort("_id",-1).limit(100)]}
