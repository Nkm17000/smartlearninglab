from fastapi import APIRouter, Depends
from app.db.mongo import get_db
from app.core.security import current_user
from datetime import datetime, timezone
import uuid

router=APIRouter(prefix="/api/v1/ai", tags=["AI"])

def clean(x):
    if isinstance(x,dict): return {k:(v.isoformat() if hasattr(v,"isoformat") else v) for k,v in x.items()}
    return x

@router.get("/conversations")
def conversations(user=Depends(current_user)):
    return [clean(x) for x in get_db().conversations.find({"user_id":user["_id"]}).sort("created_at",-1)]
@router.post("/conversations")
def create_conversation(data: dict|None=None,user=Depends(current_user)):
    d=data or {}; d.update({"_id":uuid.uuid4().hex,"user_id":user["_id"],"title":d.get("title","Study Assistant"),"created_at":datetime.now(timezone.utc)}); get_db().conversations.insert_one(d); return clean(d)
@router.get("/conversations/{conversation_id}/messages")
def messages(conversation_id:str,user=Depends(current_user)):
    return [clean(x) for x in get_db().messages.find({"conversation_id":conversation_id,"user_id":user["_id"]}).sort("created_at",1)]
@router.post("/messages")
def save_message(data:dict,user=Depends(current_user)):
    d=dict(data); d.update({"_id":uuid.uuid4().hex,"user_id":user["_id"],"created_at":datetime.now(timezone.utc)}); get_db().messages.insert_one(d); return clean(d)
