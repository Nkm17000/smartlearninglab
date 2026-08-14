from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.database import collection
from app.security import decode_token
from app.utils import oid, clean_doc

bearer = HTTPBearer(auto_error=True)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    payload = decode_token(credentials.credentials)
    user = collection("users").find_one({"_id": oid(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return clean_doc(user)

def require_admin(user=Depends(get_current_user)):
    if user.get("role") not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Admin/teacher access required")
    return user
