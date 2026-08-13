from fastapi import APIRouter, HTTPException, Depends
from app.core.dependencies import get_current_user, require_admin
from app.schemas.video import VideoCreate
from app.services.video_service import VideoService

router = APIRouter()
service = VideoService()

@router.get("")
def get_items():
    return {"status": "success", "data": service.get_all()}

@router.get("/{item_id}")
def get_item(item_id: str):
    result = service.get_by_id(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "success", "data": result}

@router.post("")
def create_item(request: VideoCreate, current_user=Depends(require_admin)):
    return {"status": "success", "data": service.create(request.model_dump())}
