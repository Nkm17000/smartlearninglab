from fastapi import APIRouter, HTTPException
from app.database import collection
from app.utils import oid, clean_doc

router=APIRouter()

def docs(name,query=None,limit=200):
    return [clean_doc(x) for x in collection(name).find(query or {}).limit(limit)]

def find(name,value):
    return collection(name).find_one({"_id":oid(value)})

@router.get("/courses")
def courses():
    return {"status":"success","data":docs("courses")}

@router.get("/courses/{course_id}")
def course(course_id:str):
    x=find("courses",course_id)
    if not x: raise HTTPException(404,"Course not found")
    return {"status":"success","data":clean_doc(x)}

@router.get("/subjects")
def subjects(course_id:str|None=None):
    q={}
    if course_id:
        q={"course_id":course_id}
    return {"status":"success","data":docs("subjects",q)}

@router.get("/lessons")
def lessons(course_id:str|None=None,subject_id:str|None=None):
    q={}
    if course_id:q["course_id"]=course_id
    if subject_id:q["subject_id"]=subject_id
    return {"status":"success","data":docs("lessons",q)}

@router.get("/lessons/{lesson_id}")
def lesson(lesson_id:str):
    x=find("lessons",lesson_id)
    if not x: raise HTTPException(404,"Lesson not found")
    return {"status":"success","data":clean_doc(x)}

@router.get("/videos")
def videos(lesson_id:str|None=None):
    return {"status":"success","data":docs("videos",{"lesson_id":lesson_id} if lesson_id else {})}

@router.get("/videos/{video_id}")
def video(video_id:str):
    x=find("videos",video_id)
    if not x: raise HTTPException(404,"Video not found")
    return {"status":"success","data":clean_doc(x)}

@router.get("/quizzes")
def quizzes(lesson_id:str|None=None):
    return {"status":"success","data":docs("quizzes",{"lesson_id":lesson_id} if lesson_id else {})}

@router.get("/quizzes/{quiz_id}")
def quiz(quiz_id:str):
    x=find("quizzes",quiz_id)
    if not x: raise HTTPException(404,"Quiz not found")
    questions=docs("questions",{"quiz_id":quiz_id})
    # Never expose answer keys to the mobile app.
    for q in questions:
        q.pop("answer",None); q.pop("correct_answer",None)
    data=clean_doc(x); data["questions"]=questions
    return {"status":"success","data":data}

@router.get("/search")
def search(q:str):
    needle=q.strip()
    if not needle: return {"status":"success","data":[]}
    regex={"$regex":needle,"$options":"i"}
    result=[]
    for name,typ in [("courses","course"),("subjects","subject"),("lessons","lesson")]:
        for x in collection(name).find({"$or":[{"title":regex},{"name":regex},{"description":regex}]}).limit(30):
            result.append({"type":typ,**clean_doc(x)})
    return {"status":"success","data":result[:50]}
