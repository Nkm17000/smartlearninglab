from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def user_out(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "student"),
        "is_active": user.get("is_active", True),
    }


@router.post("/register")
def register(data: RegisterRequest):
    db = get_db()
    email = data.email.lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already registered")
    user = {
        "_id": uuid.uuid4().hex,
        "name": data.name.strip(),
        "email": email,
        "password_hash": hash_password(data.password),
        "role": "student",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.users.insert_one(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_out(user)}


@router.post("/login")
def login(data: LoginRequest):
    user = get_db().users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(403, "Account disabled")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_out(user)}
