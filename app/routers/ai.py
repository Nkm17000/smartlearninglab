from fastapi import APIRouter, Depends
from app.core.deps import current_user
from app.db.mongo import get_db
from datetime import datetime
import uuid

router=APIRouter(prefix="/ai", tags=["AI"])

@router.get("/conversations")
def conversations(user=Depends(current_user)):
    return list(get_db().ai_conversations.find({"user_id": str(user["_id"])}).sort("updated_at",-1).limit(50))

@router.post("/conversations")
def create_conversation(data: dict | None = None, user=Depends(current_user)):
    d=dict(data or {})
    d.update({"_id":uuid.uuid4().hex,"user_id":str(user["_id"]),"title":d.get("title","Study Assistant"),"created_at":datetime.utcnow(),"updated_at":datetime.utcnow()})
    get_db().ai_conversations.insert_one(d); d["id"]=d.pop("_id"); return d

@router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, user=Depends(current_user)):
    return list(get_db().ai_messages.find({"conversation_id":conversation_id,"user_id":str(user["_id"])}).sort("created_at",1))

@router.post("/messages")
def save_message(data: dict, user=Depends(current_user)):
    d=dict(data); d.update({"_id":uuid.uuid4().hex,"user_id":str(user["_id"]),"role":"user","created_at":datetime.utcnow()})
    get_db().ai_messages.insert_one(d); d["id"]=d.pop("_id"); return d
