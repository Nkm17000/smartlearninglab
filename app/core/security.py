import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import get_settings
from app.db.mongo import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 210000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2_sha256": return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_access_token(user: dict) -> str:
    s = get_settings(); now = datetime.now(timezone.utc)
    payload = {"sub": str(user["_id"]), "role": user.get("role", "student"), "email": user.get("email"), "iat": now, "exp": now + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=["HS256"])
        uid = payload.get("sub")
        if not uid: raise HTTPException(401, "Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = get_db().users.find_one({"_id": uid})
    if not user: raise HTTPException(401, "User not found")
    if not user.get("is_active", True): raise HTTPException(403, "Account disabled")
    return user


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not credentials: raise HTTPException(401, "Authentication required")
    return decode_access_token(credentials.credentials)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") not in {"root_admin", "admin", "content_admin", "instructor", "support_admin"}:
        raise HTTPException(403, "Admin access required")
    return user


def root_admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "root_admin":
        raise HTTPException(403, "Root admin access required")
    return user
