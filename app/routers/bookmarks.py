from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.schemas.bookmarks import BookmarkCreate
from app.services.bookmarks_service.py import BookmarkService

router = APIRouter()
service = BookmarkService()

@router.get("")
def get_items(current_user=Depends(get_current_user)):
    return {"status": "success", "data": service.get_all({"user_id": current_user["_id"]})}

@router.post("")
def create_item(request: BookmarkCreate, current_user=Depends(get_current_user)):
    data = request.model_dump()
    data["user_id"] = current_user["_id"]
    return {"status": "success", "data": service.create(data)}
