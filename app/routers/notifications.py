from fastapi import APIRouter, Depends, Query
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.utils import serialize_doc

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(current_user=Depends(get_current_user), unread_only: bool = False, limit: int = Query(50, ge=1, le=200)):
    query = {"userId": current_user["id"]}
    if unread_only:
        query["read"] = False
    docs = list(get_db().notifications.find(query).sort("createdAt", -1).limit(limit))
    return [serialize_doc(x) for x in docs]


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, current_user=Depends(get_current_user)):
    from bson import ObjectId
    get_db().notifications.update_one(
        {"_id": ObjectId(notification_id), "userId": current_user["id"]},
        {"$set": {"read": True}}
    )
    return {"message": "Notification marked as read"}
