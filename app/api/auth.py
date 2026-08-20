from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from app.db.mongo import get_db
from app.core.security import hash_password, verify_password, create_access_token
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "student"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

def user_out(u):
    return {"id": str(u["_id"]), "name": u["name"], "email": u["email"], "role": u.get("role", "student")}

@router.post("/register")
def register(data: RegisterRequest):
    db = get_db(); email = data.email.lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already registered")
    role = "admin" if data.role.lower() == "admin" else "student"
    u = {"_id": uuid.uuid4().hex, "name": data.name.strip(), "email": email, "password_hash": hash_password(data.password), "role": role, "is_active": True, "created_at": datetime.now(timezone.utc)}
    db.users.insert_one(u)
    return {"access_token": create_access_token(u), "token_type": "bearer", "user": user_out(u)}

@router.post("/login")
def login(data: LoginRequest):
    u = get_db().users.find_one({"email": data.email.lower()})
    if not u or not verify_password(data.password, u.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    if not u.get("is_active", True): raise HTTPException(403, "Account disabled")
    return {"access_token": create_access_token(u), "token_type": "bearer", "user": user_out(u)}
