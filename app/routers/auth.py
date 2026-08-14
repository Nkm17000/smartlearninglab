from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.db.mongo import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.utils import now_utc, serialize_doc

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    mobile: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    mobile: str | None = None
    profile_image: str | None = None


@router.post("/register")
def register(payload: RegisterRequest):
    db = get_db()
    email = payload.email.lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")

    doc = {
        "name": payload.name.strip(),
        "email": email,
        "mobile": payload.mobile,
        "passwordHash": hash_password(payload.password),
        "role": "student",
        "status": "active",
        "profileImage": None,
        "createdAt": now_utc(),
        "updatedAt": now_utc(),
    }
    result = db.users.insert_one(doc)
    user_id = str(result.inserted_id)
    token = create_access_token(user_id, "student")
    doc["_id"] = result.inserted_id
    doc.pop("passwordHash", None)
    return {"accessToken": token, "tokenType": "bearer", "user": serialize_doc(doc)}


@router.post("/login")
def login(payload: LoginRequest):
    db = get_db()
    user = db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="User account is not active")

    token = create_access_token(str(user["_id"]), user.get("role", "student"))
    user.pop("passwordHash", None)
    return {"accessToken": token, "tokenType": "bearer", "user": serialize_doc(user)}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    db = get_db()
    from bson import ObjectId
    user = db.users.find_one({"_id": ObjectId(current_user["id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.pop("passwordHash", None)
    return serialize_doc(user)


@router.put("/me")
def update_me(payload: ProfileUpdate, current_user=Depends(get_current_user)):
    db = get_db()
    from bson import ObjectId
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        return me(current_user)
    update["updatedAt"] = now_utc()
    db.users.update_one({"_id": ObjectId(current_user["id"])}, {"$set": update})
    return me(current_user)
