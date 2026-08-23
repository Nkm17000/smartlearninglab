from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import smtplib
import ssl
import uuid
import re
from email.message import EmailMessage
from urllib.parse import urlencode
from fastapi.responses import RedirectResponse

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import get_db
from app.core.logging_config import get_logger

logger = get_logger("smart_learning_lab.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def mask_email(email: str) -> str:
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked = "*" * len(local)
        else:
            masked = local[0] + "*" * max(1, len(local) - 2) + local[-1]
        return f"{masked}@{domain}"
    except Exception:
        return "<invalid-email>"


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
        "email_verified": user.get("email_verified", True),
        "auth_provider": user.get("auth_provider", "password"),
    }


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_email(to_email: str, subject: str, body: str):
    s = get_settings()
    masked_to = mask_email(to_email)
    masked_from = mask_email(s.smtp_from or s.smtp_username) if (s.smtp_from or s.smtp_username) else "<not-set>"

    logger.info(
        "SMTP_SEND_START | to=%s | from=%s | host=%s | port=%s | tls=%s | subject=%s",
        masked_to,
        masked_from,
        s.smtp_host or "<not-set>",
        s.smtp_port,
        s.smtp_use_tls,
        subject,
    )

    if not s.smtp_host or not s.smtp_username or not s.smtp_password:
        logger.error(
            "SMTP_CONFIG_ERROR | host_set=%s | username_set=%s | password_set=%s | from_set=%s",
            bool(s.smtp_host),
            bool(s.smtp_username),
            bool(s.smtp_password),
            bool(s.smtp_from),
        )
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s.smtp_from or s.smtp_username
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        if s.smtp_use_tls:
            logger.debug("SMTP_CONNECT | mode=STARTTLS")
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
                server.starttls(context=context)
                logger.debug("SMTP_TLS_READY")
                server.login(s.smtp_username, s.smtp_password)
                logger.debug("SMTP_AUTH_SUCCESS")
                server.send_message(msg)
        else:
            logger.debug("SMTP_CONNECT | mode=SSL")
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=20) as server:
                server.login(s.smtp_username, s.smtp_password)
                logger.debug("SMTP_AUTH_SUCCESS")
                server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "SMTP_AUTH_FAILED | to=%s | code=%s | message=%s",
            masked_to,
            getattr(exc, "smtp_code", "unknown"),
            getattr(exc, "smtp_error", b"").decode(errors="replace") if isinstance(getattr(exc, "smtp_error", b""), bytes) else str(getattr(exc, "smtp_error", "")),
        )
        raise
    except Exception:
        logger.exception("SMTP_SEND_FAILED | to=%s", masked_to)
        raise

    logger.info("SMTP_SEND_SUCCESS | to=%s | subject=%s", masked_to, subject)


@router.post("/register")
def register(data: RegisterRequest):
    logger.info("AUTH_REGISTER_START | email=%s", mask_email(str(data.email)))
    db = get_db()
    email = data.email.lower()
    # Reject ANY existing account before creating a verification token or sending email.
    # This includes accounts that registered earlier but never confirmed their email.
    # Use a case-insensitive lookup so Student@Example.com and student@example.com
    # cannot create separate registrations.
    existing = db.users.find_one({
        "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    })
    if existing:
        logger.warning(
            "AUTH_REGISTER_DUPLICATE_EMAIL | email=%s | user_id=%s | verified=%s",
            mask_email(email),
            existing.get("_id"),
            bool(existing.get("email_verified", False)),
        )
        raise HTTPException(
            status_code=409,
            detail="Email already exists. Please login or use another email.",
        )

    user_id = uuid.uuid4().hex
    user = {
        "_id": user_id,
        "name": data.name.strip(),
        "email": email,
        "password_hash": hash_password(data.password),
        "role": "student",
        "is_active": False,
        "email_verified": False,
        "auth_provider": "password",
        "created_at": now(),
        "updated_at": now(),
    }
    db.users.insert_one(user)

    raw = secrets.token_urlsafe(48)
    db.email_verification_tokens.delete_many({"user_id": user_id})
    db.email_verification_tokens.insert_one({
        "_id": uuid.uuid4().hex,
        "user_id": user_id,
        "token_hash": token_hash(raw),
        "expires_at": now() + timedelta(hours=get_settings().email_verification_hours),
        "created_at": now(),
    })

    s = get_settings()
    verify_url = f"{s.backend_public_url.rstrip('/')}/api/v1/auth/verify-email?token={raw}"
    body = (
        f"Hello {user.get('name', 'Student')},\n\n"
        "Welcome to Smart Learning Lab!\n\n"
        "Please confirm your email address to complete your student registration.\n\n"
        f"Confirm your email: {verify_url}\n\n"
        f"This confirmation link expires in {s.email_verification_hours} hours.\n"
        "Your account will remain inactive until you confirm this email.\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    try:
        send_email(email, "Confirm your Smart Learning Lab account", body)
    except Exception as exc:
        # Do not leave an account that can never be activated when SMTP is broken.
        db.email_verification_tokens.delete_many({"user_id": user_id})
        db.users.delete_one({"_id": user_id})
        print(f"Registration email failed: {exc}")
        raise HTTPException(503, "Registration email could not be sent. Please try again later.")

    logger.info("AUTH_REGISTER_SUCCESS | email=%s | verification_required=true", mask_email(email))
    return {
        "verification_required": True,
        "message": "Registration request created successfully. Please confirm your email to complete registration.",
        "email": email,
    }


@router.post("/register/resend")
def resend_registration(data: ForgotPasswordRequest):
    email = data.email.lower()
    logger.info("AUTH_RESEND_VERIFICATION_START | email=%s", mask_email(email))
    db = get_db()
    user = db.users.find_one({"email": email})
    if not user or user.get("email_verified", False):
        logger.info("AUTH_RESEND_VERIFICATION_NO_PENDING_REGISTRATION | email=%s", mask_email(email))
        return {"verification_required": False, "message": "If a pending registration exists, a confirmation email has been sent."}
    raw = secrets.token_urlsafe(48)
    db.email_verification_tokens.delete_many({"user_id": user["_id"]})
    db.email_verification_tokens.insert_one({"_id": uuid.uuid4().hex, "user_id": user["_id"], "token_hash": token_hash(raw), "expires_at": now() + timedelta(hours=get_settings().email_verification_hours), "created_at": now()})
    s = get_settings()
    verify_url = f"{s.backend_public_url.rstrip('/')}/api/v1/auth/verify-email?token={raw}"
    body = (f"Hello {user.get('name', 'Student')},\n\nPlease confirm your Smart Learning Lab registration.\n\n"
            f"Confirm your email: {verify_url}\n\nThis link expires in {s.email_verification_hours} hours.\n")
    try:
        send_email(email, "Confirm your Smart Learning Lab account", body)
    except Exception as exc:
        db.email_verification_tokens.delete_many({"user_id": user["_id"]})
        logger.exception("AUTH_RESEND_VERIFICATION_EMAIL_FAILED | user_id=%s | email=%s | error_type=%s | error=%s", user.get("_id"), mask_email(email), type(exc).__name__, str(exc))
        raise HTTPException(503, "Confirmation email could not be sent. Check the backend logs and try again.")
    logger.info("AUTH_RESEND_VERIFICATION_SUCCESS | user_id=%s | email=%s", user.get("_id"), mask_email(email))
    return {"verification_required": True, "message": "Confirmation email sent successfully. Please check your email.", "email": email}


@router.post("/verify-email/request")
def request_email_verification(data: ForgotPasswordRequest):
    return resend_registration(data)


@router.get("/verify-email")
def verify_email_link(token: str):
    logger.info("AUTH_VERIFY_EMAIL_START")
    db = get_db()
    row = db.email_verification_tokens.find_one({"token_hash": token_hash(token)})
    s = get_settings()
    if not row or row.get("expires_at", now()) <= now():
        return RedirectResponse(f"{s.frontend_web_url.rstrip('/')}/?verified=failed", status_code=303)

    user = db.users.find_one({"_id": row["user_id"]})
    if not user:
        return RedirectResponse(f"{s.frontend_web_url.rstrip('/')}/?verified=failed", status_code=303)

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True, "is_active": True, "updated_at": now()}}
    )
    db.email_verification_tokens.delete_many({"user_id": user["_id"]})
    logger.info("AUTH_VERIFY_EMAIL_SUCCESS | user_id=%s", user.get("_id"))
    return RedirectResponse(f"{s.frontend_web_url.rstrip('/')}/?verified=success", status_code=303)


@router.post("/login")
def login(data: LoginRequest):
    logger.info("AUTH_LOGIN_START | email=%s", mask_email(str(data.email)))
    user = get_db().users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    # Email confirmation is mandatory for newly registered students. Legacy accounts
    # without the field remain compatible and are treated as already verified.
    if user.get("role", "student") == "student" and user.get("email_verified", True) is False:
        raise HTTPException(403, "Please confirm your email address before signing in.")
    if not user.get("is_active", True):
        raise HTTPException(403, "Account disabled")
    logger.info("AUTH_LOGIN_SUCCESS | user_id=%s | role=%s", user.get("_id"), user.get("role", "student"))
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(token: str = Query(...)):
    # OAuth callback helper. Token is already a signed JWT.
    from app.core.security import decode_access_token
    user = decode_access_token(token)
    return {"user": user_out(user)}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    email = data.email.lower()
    logger.info("AUTH_FORGOT_PASSWORD_START | email=%s", mask_email(email))
    db = get_db()
    user = db.users.find_one({"email": email})
    # Always return the same response to avoid email enumeration.
    response = {"message": "If the email exists, a password reset link has been sent."}
    if not user:
        logger.info("AUTH_FORGOT_PASSWORD_USER_NOT_FOUND | email=%s", mask_email(email))
        return response
    if not user.get("is_active", True):
        logger.info("AUTH_FORGOT_PASSWORD_INACTIVE_USER | user_id=%s", user.get("_id"))
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
        # Local debugging: log the complete exception server-side, but never expose
        # SMTP credentials or internals to the client. Also remove the unused token.
        db.password_reset_tokens.delete_many({"user_id": user["_id"]})
        logger.exception(
            "AUTH_FORGOT_PASSWORD_EMAIL_FAILED | user_id=%s | email=%s | error_type=%s | error=%s",
            user.get("_id"),
            mask_email(user.get("email", "")),
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(503, "Unable to send the password reset email. Check the backend logs.")
    logger.info("AUTH_FORGOT_PASSWORD_SUCCESS | user_id=%s | email=%s", user.get("_id"), mask_email(user.get("email", "")))
    return response


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    logger.info("AUTH_RESET_PASSWORD_START")
    db = get_db()
    record = db.password_reset_tokens.find_one({"token_hash": token_hash(data.token)})
    if not record or record.get("expires_at", now()) <= now():
        raise HTTPException(400, "Reset link is invalid or expired")

    user = db.users.find_one({"_id": record["user_id"]})
    if not user:
        raise HTTPException(400, "User not found")

    db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(data.password), "auth_provider": "password", "updated_at": now()}})
    db.password_reset_tokens.delete_many({"user_id": user["_id"]})
    logger.info("AUTH_RESET_PASSWORD_SUCCESS | user_id=%s", user.get("_id"))
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
