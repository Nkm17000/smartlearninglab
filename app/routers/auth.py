from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError
from app.db.mongo import get_db
from app.schemas.common import RegisterRequest, LoginRequest, TokenResponse, UserOut
from app.core.security import hash_password, verify_password, create_access_token
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])

def user_out(u):
    return UserOut(id=str(u["_id"]), name=u["name"], email=u["email"], role=u["role"])

@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest):
    db = get_db()
    email = data.email.lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already registered")
    role = "student"  # public registration cannot create admins
    user = {
        "_id": uuid.uuid4().hex,
        "name": data.name,
        "email": email,
        "password_hash": hash_password(data.password),
        "role": role,
        "created_at": __import__("datetime").datetime.utcnow(),
    }
    db.users.insert_one(user)
    return {
        "access_token": create_access_token(user["_id"], role, email),
        "token_type": "bearer",
        "user": user_out(user),
    }

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    user = get_db().users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return {
        "access_token": create_access_token(str(user["_id"]), user["role"], user["email"]),
        "token_type": "bearer",
        "user": user_out(user),
    }
