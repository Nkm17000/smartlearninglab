from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.utils import serialize_doc

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("/dashboard")
def dashboard(exam_id: str | None = None, current_user=Depends(get_current_user)):
    db = get_db()
    uid = current_user["id"]
    query = {"userId": uid}
    if exam_id:
        query["examId"] = exam_id

    progress = db.student_progress.find_one(query, sort=[("updatedAt", -1)]) or {}
    mastery = list(db.student_topic_mastery.find({"userId": uid}).sort("score", 1).limit(20))
    mistakes = db.student_mistakes.count_documents({"userId": uid})
    revision = db.student_revision_queue.count_documents({"userId": uid, "dueAt": {"$lte": datetime.now(timezone.utc)}})
    attempts = db.test_attempts.count_documents({"userId": uid, "status": "submitted"})

    return {
        "progress": serialize_doc(progress),
        "weakTopics": [serialize_doc(x) for x in mastery if float(x.get("score", 0)) < 60],
        "mistakeCount": mistakes,
        "revisionDue": revision,
        "completedTests": attempts,
    }


class MasteryRequest(BaseModel):
    examId: str | None = None
    topicId: str
    score: float = Field(ge=0, le=100)
    level: str | None = None


@router.post("/mastery")
def update_mastery(payload: MasteryRequest, current_user=Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    data = payload.model_dump()
    data.update({"userId": current_user["id"], "updatedAt": now})
    db.student_topic_mastery.update_one(
        {"userId": current_user["id"], "topicId": payload.topicId},
        {"$set": data, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return serialize_doc(db.student_topic_mastery.find_one({"userId": current_user["id"], "topicId": payload.topicId}))


@router.post("/mistakes/{question_id}")
def add_mistake(question_id: str, current_user=Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    db.student_mistakes.update_one(
        {"userId": current_user["id"], "questionId": question_id},
        {"$inc": {"count": 1}, "$set": {"lastSeenAt": now}, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return {"message": "Added to mistake book"}


@router.get("/mistakes")
def mistakes(current_user=Depends(get_current_user), limit: int = Query(100, ge=1, le=500)):
    docs = list(db.student_mistakes.find({"userId": current_user["id"]}).sort("lastSeenAt", -1).limit(limit)) if (db := get_db()) else []
    return [serialize_doc(x) for x in docs]


@router.get("/revision")
def revision(current_user=Depends(get_current_user), limit: int = Query(50, ge=1, le=200)):
    now = datetime.now(timezone.utc)
    docs = list(get_db().student_revision_queue.find({"userId": current_user["id"], "dueAt": {"$lte": now}}).sort("dueAt", 1).limit(limit))
    return [serialize_doc(x) for x in docs]
