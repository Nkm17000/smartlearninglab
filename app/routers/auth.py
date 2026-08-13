from fastapi import APIRouter, HTTPException
from app.schemas.auth import RegisterRequest, LoginRequest
from app.services.auth_service import AuthService

router = APIRouter()
service = AuthService()

@router.post("/register")
def register(request: RegisterRequest):
    try:
        return service.register(request.name, request.email, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.post("/login")
def login(request: LoginRequest):
    try:
        return service.login(request.email, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
