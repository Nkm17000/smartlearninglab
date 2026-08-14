from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db.mongo import get_db
from app.core.security import get_current_user
from app.utils import serialize_doc

router = APIRouter(prefix="/ai", tags=["AI"])


class ConversationRequest(BaseModel):
    title: str | None = None
    examId: str | None = None
    topicId: str | None = None


class MessageRequest(BaseModel):
    conversationId: str
    message: str = Field(min_length=1, max_length=10000)
    language: str = "en"
    contextType: str | None = None
    contextId: str | None = None


@router.post("/conversations")
def create_conversation(payload: ConversationRequest, current_user=Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"userId": current_user["id"], "createdAt": now, "updatedAt": now})
    result = db.ai_conversations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/conversations")
def conversations(current_user=Depends(get_current_user)):
    docs = list(get_db().ai_conversations.find({"userId": current_user["id"]}).sort("updatedAt", -1))
    return [serialize_doc(x) for x in docs]


@router.post("/messages")
def save_message(payload: MessageRequest, current_user=Depends(get_current_user)):
    db = get_db()
    conversation = db.ai_conversations.find_one(
        {"_id": ObjectId(payload.conversationId), "userId": current_user["id"]}
    )
    if not conversation:
        from fastapi import HTTPException
        raise HTTPException(404, "Conversation not found")

    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"userId": current_user["id"], "role": "user", "createdAt": now})
    result = db.ai_messages.insert_one(doc)
    db.ai_conversations.update_one({"_id": conversation["_id"]}, {"$set": {"updatedAt": now}})
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, current_user=Depends(get_current_user)):
    docs = list(get_db().ai_messages.find(
        {"conversationId": conversation_id, "userId": current_user["id"]}
    ).sort("createdAt", 1))
    return [serialize_doc(x) for x in docs]
