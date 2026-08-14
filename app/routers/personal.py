from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.utils import serialize_doc

router = APIRouter(prefix="/me", tags=["Personal"])


class NoteRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str
    entityType: str | None = None
    entityId: str | None = None


class StudyGoalRequest(BaseModel):
    examId: str
    title: str
    targetDate: str | None = None
    minutesPerDay: int = Field(default=60, ge=1, le=1440)


@router.get("/bookmarks")
def bookmarks(current_user=Depends(get_current_user)):
    docs = list(get_db().bookmarks.find({"userId": current_user["id"]}).sort("createdAt", -1))
    return [serialize_doc(x) for x in docs]


@router.get("/favorites")
def favorites(current_user=Depends(get_current_user)):
    docs = list(get_db().favorites.find({"userId": current_user["id"]}).sort("createdAt", -1))
    return [serialize_doc(x) for x in docs]


@router.post("/notes")
def create_note(payload: NoteRequest, current_user=Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"userId": current_user["id"], "createdAt": now, "updatedAt": now})
    result = db.student_notes.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/notes")
def notes(current_user=Depends(get_current_user)):
    docs = list(get_db().student_notes.find({"userId": current_user["id"]}).sort("updatedAt", -1))
    return [serialize_doc(x) for x in docs]


@router.post("/goals")
def create_goal(payload: StudyGoalRequest, current_user=Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"userId": current_user["id"], "status": "active", "createdAt": now, "updatedAt": now})
    result = db.user_goals.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/goals")
def goals(current_user=Depends(get_current_user)):
    return [serialize_doc(x) for x in get_db().user_goals.find({"userId": current_user["id"]}).sort("createdAt", -1)]
