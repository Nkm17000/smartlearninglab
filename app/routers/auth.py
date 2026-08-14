from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from app.database import collection
from app.security import hash_password, verify_password, create_token
from app.utils import clean_doc, now

router=APIRouter()

class Register(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    email:EmailStr
    password:str=Field(min_length=6,max_length=128)

class Login(BaseModel):
    email:EmailStr
    password:str

@router.post("/register")
def register(x:Register):
    email=x.email.lower()
    if collection("users").find_one({"email":email}):
        raise HTTPException(400,"Email is already registered")
    doc={"name":x.name.strip(),"email":email,"password_hash":hash_password(x.password),
         "role":"student","created_at":now()}
    r=collection("users").insert_one(doc)
    user=collection("users").find_one({"_id":r.inserted_id})
    return {"status":"success","data":{"access_token":create_token(r.inserted_id,"student"),
            "user":clean_doc(user)}}

@router.post("/login")
def login(x:Login):
    email=x.email.lower()
    user=collection("users").find_one({"email":email})
    if not user:
        raise HTTPException(401,"Invalid email or password")
    stored=user.get("password_hash") or user.get("password")
    if not stored or not verify_password(x.password,stored):
        raise HTTPException(401,"Invalid email or password")
    role=user.get("role","student")
    return {"status":"success","data":{"access_token":create_token(user["_id"],role),
            "user":clean_doc(user)}}
