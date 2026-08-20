from fastapi import APIRouter, Depends
from app.db.mongo import get_db
from app.core.deps import current_user
from datetime import datetime
import uuid

router = APIRouter(tags=["Personal"])


@router.get("/profile")
def profile(user=Depends(current_user)):
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
    }


@router.get("/progress")
def progress(user=Depends(current_user)):
    return list(get_db().progress.find({"user_id": str(user["_id"])}).limit(500))


@router.get("/mistakes")
def mistakes(user=Depends(current_user)):
    return list(get_db().mistakes.find({"user_id": str(user["_id"])}).limit(200))


@router.get("/notes")
def notes(user=Depends(current_user)):
    return list(get_db().notes.find({"user_id": str(user["_id"])}).limit(200))


@router.post("/notes")
def add_note(data: dict, user=Depends(current_user)):
    d = dict(data)
    d["_id"] = uuid.uuid4().hex
    d["user_id"] = str(user["_id"])
    d["created_at"] = datetime.utcnow()
    get_db().notes.insert_one(d)
    d["id"] = d.pop("_id")
    return d
