from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongo import get_db
from app.core.security import admin_user
from datetime import datetime, timezone
import uuid

router=APIRouter(prefix="/api/v1/admin", tags=["Admin"])
ALLOWED={"exams","subjects","topics","courses","lessons","questions","mock_tests","quizzes","current_affairs"}

def clean(x):
    if isinstance(x,dict): return {k:(v.isoformat() if hasattr(v,"isoformat") else v) for k,v in x.items()}
    return x

def ensure(data, kind):
    d=dict(data)
    d.setdefault("_id",uuid.uuid4().hex)
    d.setdefault("created_at",datetime.now(timezone.utc))
    d.setdefault("updated_at",datetime.now(timezone.utc))
    if kind in {"courses","lessons","questions","mock_tests","quizzes"}: d.setdefault("is_published",False)
    return d

@router.get("/dashboard")
def dashboard(user=Depends(admin_user)):
    db=get_db()
    return {"admin":{"id":user["_id"],"name":user["name"]},"counts":{c:db[c].count_documents({}) for c in ["users","courses","lessons","questions","quizzes","mock_tests"]},"published":{c:db[c].count_documents({"is_published":True}) for c in ["courses","lessons","questions","quizzes","mock_tests"]}}

@router.get("/{collection}")
def list_items(collection:str, search:str|None=None, limit:int=Query(100,ge=1,le=500), user=Depends(admin_user)):
    if collection not in ALLOWED: raise HTTPException(400,"Unsupported collection")
    q={}
    if search:
        q={"$or":[{"name":{"$regex":search,"$options":"i"}},{"title":{"$regex":search,"$options":"i"}},{"question":{"$regex":search,"$options":"i"}}]}
    return [clean(x) for x in get_db()[collection].find(q).sort("created_at",-1).limit(limit)]

@router.post("/{collection}")
def create_item(collection:str,data:dict,user=Depends(admin_user)):
    if collection not in ALLOWED: raise HTTPException(400,"Unsupported collection")
    d=ensure(data,collection); get_db()[collection].insert_one(d); return clean(d)

@router.put("/{collection}/{item_id}")
def update_item(collection:str,item_id:str,data:dict,user=Depends(admin_user)):
    if collection not in ALLOWED: raise HTTPException(400,"Unsupported collection")
    data=dict(data); data.pop("_id",None); data["updated_at"]=datetime.now(timezone.utc)
    r=get_db()[collection].update_one({"_id":item_id},{"$set":data})
    if not r.matched_count: raise HTTPException(404,"Item not found")
    return clean(get_db()[collection].find_one({"_id":item_id}))

@router.delete("/{collection}/{item_id}")
def delete_item(collection:str,item_id:str,user=Depends(admin_user)):
    if collection not in ALLOWED: raise HTTPException(400,"Unsupported collection")
    r=get_db()[collection].delete_one({"_id":item_id})
    if not r.deleted_count: raise HTTPException(404,"Item not found")
    return {"message":"Deleted"}

# Professional aliases: these keep the Admin FE readable while using the same storage.
@router.post("/courses/{course_id}/modules")
def create_module(course_id:str,data:dict,user=Depends(admin_user)):
    data["course_id"]=course_id; return create_item("topics",data,user)
@router.get("/courses/{course_id}/modules")
def list_modules(course_id:str,user=Depends(admin_user)):
    return list_items("topics",limit=500,user=user) if not course_id else [clean(x) for x in get_db().topics.find({"course_id":course_id}).sort("order",1)]
@router.post("/modules/{module_id}/lessons")
def create_lesson(module_id:str,data:dict,user=Depends(admin_user)):
    data["topic_id"]=module_id; topic=get_db().topics.find_one({"_id":module_id});
    if topic and topic.get("course_id"): data.setdefault("course_id",topic["course_id"])
    return create_item("lessons",data,user)
@router.get("/modules/{module_id}/lessons")
def list_lessons(module_id:str,user=Depends(admin_user)):
    return [clean(x) for x in get_db().lessons.find({"topic_id":module_id}).sort("order",1)]
@router.post("/quizzes/{quiz_id}/questions")
def add_quiz_question(quiz_id:str,data:dict,user=Depends(admin_user)):
    qid=data.get("question_id")
    if not qid: raise HTTPException(400,"question_id is required")
    q=get_db().quizzes.find_one({"_id":quiz_id})
    if not q: raise HTTPException(404,"Quiz not found")
    ids=q.get("question_ids",[])
    if qid not in ids: ids.append(qid)
    get_db().quizzes.update_one({"_id":quiz_id},{"$set":{"question_ids":ids,"updated_at":datetime.now(timezone.utc)}})
    return {"quiz_id":quiz_id,"question_ids":ids}
@router.delete("/quizzes/{quiz_id}/questions/{question_id}")
def remove_quiz_question(quiz_id:str,question_id:str,user=Depends(admin_user)):
    get_db().quizzes.update_one({"_id":quiz_id},{"$pull":{"question_ids":question_id},"$set":{"updated_at":datetime.now(timezone.utc)}})
    return {"message":"Question removed"}
