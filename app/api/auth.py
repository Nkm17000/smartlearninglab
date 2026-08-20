from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def now():
    return datetime.now(timezone.utc)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=8, max_length=128)



def user_out(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "student"),
        "is_active": user.get("is_active", True),
        "auth_provider": user.get("auth_provider", "password"),
    }


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_email(to_email: str, subject: str, body: str):
    s = get_settings()
    if not s.smtp_host or not s.smtp_username or not s.smtp_password:
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s.smtp_from or s.smtp_username
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    if s.smtp_use_tls:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
            server.starttls(context=context)
            server.login(s.smtp_username, s.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=20) as server:
            server.login(s.smtp_username, s.smtp_password)
            server.send_message(msg)


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
        "auth_provider": "password",
        "created_at": now(),
        "updated_at": now(),
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


@router.get("/me")
def me(token: str = Query(...)):
    # OAuth callback helper. Token is already a signed JWT.
    from app.core.security import decode_access_token
    user = decode_access_token(token)
    return {"user": user_out(user)}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    db = get_db()
    user = db.users.find_one({"email": data.email.lower()})
    # Always return the same response to avoid email enumeration.
    response = {"message": "If the email exists, a password reset link has been sent."}
    if not user or not user.get("is_active", True):
        return response

    raw = secrets.token_urlsafe(48)
    db.password_reset_tokens.delete_many({"user_id": user["_id"]})
    db.password_reset_tokens.insert_one({
        "_id": uuid.uuid4().hex,
        "user_id": user["_id"],
        "token_hash": token_hash(raw),
        "expires_at": now() + timedelta(minutes=get_settings().password_reset_minutes),
        "created_at": now(),
    })

    reset_url = f"{get_settings().frontend_web_url.rstrip('/')}/?reset_token={raw}"
    body = (
        f"Hello {user.get('name', 'there')},\n\n"
        "We received a request to reset your Smart Learning Lab password.\n\n"
        f"Reset your password here:\n{reset_url}\n\n"
        f"This link expires in {get_settings().password_reset_minutes} minutes.\n"
        "If you did not request this, you can safely ignore this email.\n"
    )
    try:
        send_email(user["email"], "Smart Learning Lab password reset", body)
    except Exception as exc:
        # Do not leak SMTP internals to the client.
        print(f"Password reset email failed: {exc}")
    return response


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    db = get_db()
    record = db.password_reset_tokens.find_one({"token_hash": token_hash(data.token)})
    if not record or record.get("expires_at", now()) <= now():
        raise HTTPException(400, "Reset link is invalid or expired")

    user = db.users.find_one({"_id": record["user_id"]})
    if not user:
        raise HTTPException(400, "User not found")

    db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(data.password), "auth_provider": "password", "updated_at": now()}})
    db.password_reset_tokens.delete_many({"user_id": user["_id"]})
    return {"message": "Password reset successful. You can now sign in."}


# ---------------- OAuth ----------------

def validate_oauth_redirect(redirect_uri: str) -> str:
    s = get_settings()
    allowed_web = s.frontend_web_url.rstrip("/")
    allowed_mobile = s.frontend_mobile_scheme.rstrip("/")
    if redirect_uri.rstrip("/") == allowed_web:
        return redirect_uri
    if redirect_uri.startswith(allowed_mobile + "/") or redirect_uri.startswith(s.frontend_mobile_scheme):
        return redirect_uri
    raise HTTPException(400, "Unsupported OAuth redirect URI")


def oauth_state(provider: str, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(32)
    get_db().oauth_states.insert_one({
        "_id": state,
        "provider": provider,
        "redirect_uri": redirect_uri,
        "expires_at": now() + timedelta(minutes=10),
    })
    return state


def get_oauth_state(provider: str, state: str):
    db = get_db()
    row = db.oauth_states.find_one({"_id": state, "provider": provider})
    if not row or row.get("expires_at", now()) <= now():
        raise HTTPException(400, "OAuth state is invalid or expired")
    db.oauth_states.delete_one({"_id": state})
    return row


def upsert_social_user(email: str, name: str, provider: str, provider_id: str):
    db = get_db()
    email = email.lower()
    user = db.users.find_one({"email": email})
    if user:
        db.users.update_one({"_id": user["_id"]}, {"$set": {
            "name": name or user.get("name", ""),
            "oauth_provider": provider,
            "oauth_provider_id": str(provider_id),
            "updated_at": now(),
        }})
        return db.users.find_one({"_id": user["_id"]})

    user = {
        "_id": uuid.uuid4().hex,
        "name": name or email.split("@")[0],
        "email": email,
        "password_hash": "",
        "role": "student",
        "is_active": True,
        "auth_provider": provider,
        "oauth_provider": provider,
        "oauth_provider_id": str(provider_id),
        "created_at": now(),
        "updated_at": now(),
    }
    db.users.insert_one(user)
    return user


@router.get("/{provider}/start")
def oauth_start(provider: str, redirect_uri: str):
    s = get_settings()
    provider = provider.lower()
    redirect_uri = validate_oauth_redirect(redirect_uri)
    state = oauth_state(provider, redirect_uri)

    if provider == "google":
        if not s.google_client_id:
            raise HTTPException(503, "Google OAuth is not configured")
        params = urlencode({
            "client_id": s.google_client_id,
            "redirect_uri": s.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        })
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

    if provider == "github":
        if not s.github_client_id:
            raise HTTPException(503, "GitHub OAuth is not configured")
        params = urlencode({
            "client_id": s.github_client_id,
            "redirect_uri": s.github_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        })
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")

    raise HTTPException(404, "Unsupported OAuth provider")


@router.get("/{provider}/callback")
def oauth_callback(provider: str, code: str, state: str):
    s = get_settings()
    provider = provider.lower()
    row = get_oauth_state(provider, state)

    if provider == "google":
        if not s.google_client_id or not s.google_client_secret:
            raise HTTPException(503, "Google OAuth is not configured")
        token_response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": s.google_redirect_uri,
            "grant_type": "authorization_code",
        }, timeout=20)
        if not token_response.ok:
            raise HTTPException(400, "Google authorization failed")
        access = token_response.json().get("access_token")
        profile = requests.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access}"}, timeout=20)
        if not profile.ok:
            raise HTTPException(400, "Could not read Google profile")
        p = profile.json()
        email = p.get("email")
        if not email:
            raise HTTPException(400, "Google account has no email")
        user = upsert_social_user(email, p.get("name", ""), "google", p.get("sub", ""))

    elif provider == "github":
        if not s.github_client_id or not s.github_client_secret:
            raise HTTPException(503, "GitHub OAuth is not configured")
        token_response = requests.post("https://github.com/login/oauth/access_token", data={
            "client_id": s.github_client_id,
            "client_secret": s.github_client_secret,
            "code": code,
            "redirect_uri": s.github_redirect_uri,
        }, headers={"Accept": "application/json"}, timeout=20)
        if not token_response.ok:
            raise HTTPException(400, "GitHub authorization failed")
        access = token_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
        profile = requests.get("https://api.github.com/user", headers=headers, timeout=20)
        if not profile.ok:
            raise HTTPException(400, "Could not read GitHub profile")
        p = profile.json()
        email = p.get("email")
        if not email:
            emails = requests.get("https://api.github.com/user/emails", headers=headers, timeout=20)
            if emails.ok:
                candidates = emails.json()
                primary = next((x for x in candidates if x.get("primary") and x.get("verified")), None)
                email = (primary or (candidates[0] if candidates else {})).get("email")
        if not email:
            raise HTTPException(400, "GitHub account has no accessible email")
        user = upsert_social_user(email, p.get("name") or p.get("login", ""), "github", p.get("id", ""))
    else:
        raise HTTPException(404, "Unsupported OAuth provider")

    if not user.get("is_active", True):
        raise HTTPException(403, "Account disabled")

    token = create_access_token(user)
    redirect_uri = row["redirect_uri"]
    sep = "&" if "?" in redirect_uri else "?"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode({'oauth_token': token})}")
