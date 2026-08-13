from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.services.user_service import UserService

router = APIRouter()
service = UserService()

@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    user = service.get_by_id(str(current_user["_id"]))
    if user:
        user.pop("password_hash", None)
    return {"status": "success", "data": user}

@router.get("")
def get_users(current_user=Depends(get_current_user)):
    return {"status": "success", "data": service.get_all()}
