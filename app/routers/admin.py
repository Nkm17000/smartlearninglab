from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import get_db
from app.core.deps import require_admin
from app.schemas.common import EntityCreate, QuestionCreate
import uuid
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin"])

COLLECTIONS = ["exams","subjects","topics","courses","lessons","questions","mock_tests","current_affairs"]

def clean(d):
    if not d: return None
    d["id"] = str(d.pop("_id"))
    return d

@router.get("/dashboard")
def dashboard(admin=Depends(require_admin)):
    db=get_db()
    return {c: db[c].count_documents({}) for c in ["users","exams","subjects","topics","courses","lessons","questions","mock_tests","current_affairs"]}

@router.get("/{collection}")
def list_items(collection: str, admin=Depends(require_admin)):
    if collection not in COLLECTIONS: raise HTTPException(404, "Unknown collection")
    return [clean(x) for x in get_db()[collection].find().sort("order",1).limit(500)]

@router.post("/{collection}")
def create_item(collection: str, data: dict, admin=Depends(require_admin)):
    if collection not in COLLECTIONS: raise HTTPException(404, "Unknown collection")
    data = dict(data)
    data["_id"] = uuid.uuid4().hex
    data["created_at"] = datetime.utcnow()
    get_db()[collection].insert_one(data)
    return clean(data)

@router.put("/{collection}/{item_id}")
def update_item(collection: str, item_id: str, data: dict, admin=Depends(require_admin)):
    if collection not in COLLECTIONS: raise HTTPException(404, "Unknown collection")
    data = dict(data)
    data.pop("_id", None); data.pop("id", None)
    data["updated_at"] = datetime.utcnow()
    r=get_db()[collection].update_one({"_id": item_id},{"$set":data})
    if not r.matched_count: raise HTTPException(404, "Not found")
    return clean(get_db()[collection].find_one({"_id": item_id}))

@router.delete("/{collection}/{item_id}")
def delete_item(collection: str, item_id: str, admin=Depends(require_admin)):
    if collection not in COLLECTIONS: raise HTTPException(404, "Unknown collection")
    r=get_db()[collection].delete_one({"_id": item_id})
    if not r.deleted_count: raise HTTPException(404, "Not found")
    return {"success": True}
