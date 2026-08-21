from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import current_user
from app.db.mongo import get_db

router = APIRouter(prefix="/api/v1/ai", tags=["AI Study Tutor"])


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@router.get("/conversations")
def conversations(user=Depends(current_user)):
    return [clean(x) for x in get_db().conversations.find({"user_id": str(user["_id"])}).sort("created_at", -1)]


@router.post("/conversations")
def create_conversation(data: dict | None = None, user=Depends(current_user)):
    d = dict(data or {})
    d.update({"_id": uuid.uuid4().hex, "user_id": str(user["_id"]), "title": d.get("title", "Study Assistant"), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    get_db().conversations.insert_one(d)
    return clean(d)


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, user=Depends(current_user)):
    item = get_db().conversations.find_one({"_id": conversation_id, "user_id": str(user["_id"])})
    if not item:
        raise HTTPException(404, "Conversation not found")
    return clean(item)


@router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, user=Depends(current_user)):
    conversation = get_db().conversations.find_one({"_id": conversation_id, "user_id": str(user["_id"])})
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return [clean(x) for x in get_db().messages.find({"conversation_id": conversation_id, "user_id": str(user["_id"])}).sort("created_at", 1)]


@router.post("/messages")
def save_message(data: dict, user=Depends(current_user)):
    d = dict(data)
    conversation_id = d.get("conversationId") or d.get("conversation_id")
    if not conversation_id:
        raise HTTPException(422, "conversationId is required")
    if not get_db().conversations.find_one({"_id": conversation_id, "user_id": str(user["_id"])}):
        raise HTTPException(404, "Conversation not found")
    d.update({"_id": uuid.uuid4().hex, "user_id": str(user["_id"]), "conversation_id": conversation_id, "role": d.get("role", "user"), "created_at": datetime.now(timezone.utc)})
    get_db().messages.insert_one(d)
    get_db().conversations.update_one({"_id": conversation_id}, {"$set": {"updated_at": datetime.now(timezone.utc)}})
    return clean(d)
