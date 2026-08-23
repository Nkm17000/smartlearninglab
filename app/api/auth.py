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
from fastapi import APIRouter, HTTPException, Query, Request
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


def frontend_url_for_request(request: Request) -> str:
    """Return the frontend that initiated the request.

    This is critical for local testing: a local backend must not generate a
    reset/verification link to the production frontend, otherwise the token
    is created in the local MongoDB but the production frontend/backend tries
    to consume it from a different database.
    """
    s = get_settings()
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    configured = (s.frontend_web_url or "").strip().rstrip("/")

    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            logger.info("FRONTEND_ORIGIN_SELECTED | mode=local-loopback | origin=%s", origin)
            return origin
        if configured and origin == configured:
            logger.info("FRONTEND_ORIGIN_SELECTED | mode=configured | origin=%s", origin)
            return origin

    logger.info("FRONTEND_ORIGIN_SELECTED | mode=configured-fallback | origin=%s | configured=%s", origin or "<none>", configured)
    return configured


def backend_url_for_request(request: Request) -> str:
    """Return the public backend base URL appropriate for this request.

    Local requests use the actual loopback host/port. Production uses
    BACKEND_PUBLIC_URL so email links never accidentally point at a local
    server or an outdated host.
    """
    s = get_settings()
    host = (request.url.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return str(request.base_url).rstrip("/")
    configured = (s.backend_public_url or "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def provider_callback_uri(request: Request, provider: str) -> str:
    """Select the exact provider callback URL for local or production.

    Local development uses the actual loopback API URL. Production derives the
    callback from BACKEND_PUBLIC_URL, preventing a stale GITHUB_REDIRECT_URI or
    GOOGLE_REDIRECT_URI from causing provider redirect_uri mismatch errors.
    The resulting URL must still be registered in the provider console.
    """
    s = get_settings()
    host = (request.url.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        base = str(request.base_url).rstrip("/")
        callback = f"{base}/api/v1/auth/{provider}/callback"
        logger.info(
            "OAUTH_PROVIDER_CALLBACK_SELECTED | provider=%s | mode=local | callback=%s",
            provider,
            callback,
        )
        return callback

    backend = (s.backend_public_url or "").strip().rstrip("/")
    if backend:
        callback = f"{backend}/api/v1/auth/{provider}/callback"
    else:
        callback = s.google_redirect_uri if provider == "google" else s.github_redirect_uri

    logger.info(
        "OAUTH_PROVIDER_CALLBACK_SELECTED | provider=%s | mode=production | callback=%s",
        provider,
        callback,
    )
    return callback


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
def register(request: Request, data: RegisterRequest):
    logger.info("AUTH_REGISTER_START | email=%s", mask_email(str(data.email)))
    db = get_db()
    email = data.email.lower()

    # Case-insensitive lookup prevents duplicate accounts. A verified account is
    # still rejected, but an unverified/pending registration can register again.
    # In that case we refresh the registration details, invalidate the previous
    # verification token, create a new token and send the confirmation email again.
    existing = db.users.find_one({
        "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}
    })

    was_pending = False
    if existing:
        already_verified = bool(existing.get("email_verified", False))
        logger.info(
            "AUTH_REGISTER_EXISTING_EMAIL | email=%s | user_id=%s | verified=%s",
            mask_email(email),
            existing.get("_id"),
            already_verified,
        )

        if already_verified:
            logger.warning(
                "AUTH_REGISTER_DUPLICATE_EMAIL | email=%s | user_id=%s | verified=true",
                mask_email(email),
                existing.get("_id"),
            )
            raise HTTPException(
                status_code=409,
                detail="Email already exists. Please login or use another email.",
            )

        # Existing account is pending email confirmation. Allow the user to
        # submit registration again and send a fresh confirmation email.
        was_pending = True
        user_id = existing["_id"]
        db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "name": data.name.strip(),
                "password_hash": hash_password(data.password),
                "is_active": False,
                "email_verified": False,
                "auth_provider": "password",
                "updated_at": now(),
            }}
        )
        user = db.users.find_one({"_id": user_id}) or existing
    else:
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

    # Only the newest verification token is valid.
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
    verify_url = f"{backend_url_for_request(request)}/api/v1/auth/verify-email?token={raw}"
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
        # Do not remove an existing pending account if only SMTP temporarily fails.
        # Remove its newly created token so the previous token cannot be confused
        # with the latest registration attempt.
        db.email_verification_tokens.delete_many({"user_id": user_id})
        if not was_pending:
            db.users.delete_one({"_id": user_id})
        logger.exception(
            "AUTH_REGISTER_EMAIL_FAILED | email=%s | pending=%s | error_type=%s | error=%s",
            mask_email(email),
            was_pending,
            type(exc).__name__,
            str(exc),
        )
        raise HTTPException(503, "Registration email could not be sent. Please try again later.")

    logger.info(
        "AUTH_REGISTER_SUCCESS | email=%s | verification_required=true | resent=%s",
        mask_email(email),
        was_pending,
    )
    return {
        "verification_required": True,
        "resent": was_pending,
        "message": (
            "A new confirmation email has been sent. Please confirm your email to complete registration."
            if was_pending
            else "Registration request created successfully. Please confirm your email to complete registration."
        ),
        "email": email,
    }


@router.post("/register/resend")
def resend_registration(request: Request, data: ForgotPasswordRequest):
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
    verify_url = f"{backend_url_for_request(request)}/api/v1/auth/verify-email?token={raw}"
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
def request_email_verification(request: Request, data: ForgotPasswordRequest):
    return resend_registration(request, data)


@router.get("/verify-email")
def verify_email_link(request: Request, token: str):
    logger.info("AUTH_VERIFY_EMAIL_START")
    db = get_db()
    row = db.email_verification_tokens.find_one({"token_hash": token_hash(token)})
    expires_at = normalize_utc(row.get("expires_at")) if row else None
    if not row or not expires_at or expires_at <= now():
        logger.warning(
            "AUTH_VERIFY_EMAIL_INVALID_OR_EXPIRED | token_present=%s | expires_at=%s",
            bool(token),
            expires_at,
        )
        return RedirectResponse(f"{frontend_url_for_request(request)}/?verified=failed", status_code=303)

    user = db.users.find_one({"_id": row["user_id"]})
    if not user:
        return RedirectResponse(f"{frontend_url_for_request(request)}/?verified=failed", status_code=303)

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True, "is_active": True, "updated_at": now()}}
    )
    db.email_verification_tokens.delete_many({"user_id": user["_id"]})
    logger.info("AUTH_VERIFY_EMAIL_SUCCESS | user_id=%s", user.get("_id"))
    return RedirectResponse(f"{frontend_url_for_request(request)}/?verified=success", status_code=303)


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
def forgot_password(request: Request, data: ForgotPasswordRequest):
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

    reset_url = f"{frontend_url_for_request(request)}/?reset_token={raw}"
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
    token = str(data.token or "").strip()
    logger.info("AUTH_RESET_PASSWORD_START | token_present=%s | token_length=%s", bool(token), len(token))
    if len(token) < 20:
        raise HTTPException(400, "Reset link is invalid or incomplete. Please request a new reset email.")

    db = get_db()
    record = db.password_reset_tokens.find_one({"token_hash": token_hash(token)})
    if not record:
        logger.warning("AUTH_RESET_PASSWORD_TOKEN_NOT_FOUND")
        raise HTTPException(400, "Reset link is invalid or expired. Please request a new reset email.")

    expires_at = normalize_utc(record.get("expires_at"))
    if not expires_at or expires_at <= now():
        db.password_reset_tokens.delete_one({"_id": record.get("_id")})
        logger.warning("AUTH_RESET_PASSWORD_TOKEN_EXPIRED | expires_at=%s | now=%s", expires_at, now())
        raise HTTPException(400, "Reset link is invalid or expired. Please request a new reset email.")

    user = db.users.find_one({"_id": record["user_id"]})
    if not user:
        logger.warning("AUTH_RESET_PASSWORD_USER_NOT_FOUND | user_id=%s", record.get("user_id"))
        raise HTTPException(400, "User not found")

    result = db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hash_password(data.password),
            "auth_provider": "password",
            "is_active": True,
            "email_verified": user.get("email_verified", True),
            "updated_at": now(),
        }},
    )
    if result.modified_count != 1:
        logger.error("AUTH_RESET_PASSWORD_UPDATE_FAILED | user_id=%s | matched=%s | modified=%s", user.get("_id"), result.matched_count, result.modified_count)
        raise HTTPException(500, "Password could not be updated. Please try again.")

    db.password_reset_tokens.delete_many({"user_id": user["_id"]})
    logger.info("AUTH_RESET_PASSWORD_SUCCESS | user_id=%s | email=%s", user.get("_id"), mask_email(user.get("email", "")))
    return {"message": "Password reset successful. You can now sign in."}


# ---------------- OAuth ----------------

def validate_oauth_redirect(redirect_uri: str) -> str:
    """Validate the FE destination after OAuth."""
    from urllib.parse import urlparse

    s = get_settings()
    if not redirect_uri:
        logger.warning("OAUTH_REDIRECT_REJECTED | reason=empty")
        raise HTTPException(400, "Unsupported OAuth redirect URI")

    candidate = redirect_uri.strip().rstrip("/")
    allowed_web = (s.frontend_web_url or "").strip().rstrip("/")
    allowed_mobile = (s.frontend_mobile_scheme or "").strip().rstrip("/")

    if allowed_web and candidate == allowed_web:
        logger.info("OAUTH_REDIRECT_ACCEPTED | mode=configured | redirect=%s", redirect_uri)
        return redirect_uri

    requested = urlparse(candidate)

    # Mobile custom scheme. Accept smartlearninglab://oauth, smartlearninglab://...
    mobile_scheme = urlparse(allowed_mobile + "//").scheme if allowed_mobile else ""
    if mobile_scheme and requested.scheme.lower() == mobile_scheme.lower():
        logger.info("OAUTH_REDIRECT_ACCEPTED | mode=mobile | redirect=%s", redirect_uri)
        return redirect_uri

    # Expo Web local development can run on localhost or 127.0.0.1 and its port
    # may change. Only loopback hosts are accepted here; arbitrary hosts remain rejected.
    loopback = {"localhost", "127.0.0.1", "::1"}
    if requested.scheme in {"http", "https"} and requested.hostname in loopback:
        logger.info("OAUTH_REDIRECT_ACCEPTED | mode=local-loopback | redirect=%s", redirect_uri)
        return redirect_uri

    logger.warning(
        "OAUTH_REDIRECT_REJECTED | requested=%s | configured_web=%s | configured_mobile=%s",
        redirect_uri, allowed_web, allowed_mobile
    )
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


def normalize_utc(value):
    """Normalize MongoDB/Python datetime values to timezone-aware UTC.

    Older OAuth-state documents may contain naive UTC datetimes while new
    documents use timezone-aware UTC. Python does not allow comparing those
    two datetime types directly, so every value is normalized before expiry
    validation.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_oauth_state(provider: str, state: str):
    db = get_db()

    logger.info(
        "OAUTH_STATE_LOOKUP | provider=%s | state_present=%s",
        provider,
        bool(state),
    )

    row = db.oauth_states.find_one({"_id": state, "provider": provider})

    if not row:
        logger.warning(
            "OAUTH_STATE_NOT_FOUND | provider=%s",
            provider,
        )
        raise HTTPException(400, "OAuth state is invalid or expired")

    expires_at_raw = row.get("expires_at")
    expires_at = normalize_utc(expires_at_raw)
    current_time = now()

    logger.info(
        "OAUTH_STATE_TIME_CHECK | provider=%s | expires_at=%s | now=%s",
        provider,
        expires_at,
        current_time,
    )

    if expires_at is None or expires_at <= current_time:
        logger.warning(
            "OAUTH_STATE_EXPIRED | provider=%s | expires_at=%s | now=%s",
            provider,
            expires_at,
            current_time,
        )
        db.oauth_states.delete_one({"_id": state})
        raise HTTPException(400, "OAuth state is invalid or expired")

    db.oauth_states.delete_one({"_id": state})

    logger.info(
        "OAUTH_STATE_VALID | provider=%s",
        provider,
    )

    return row


def upsert_social_user(email: str, name: str, provider: str, provider_id: str):
    """Create or link a verified student account for a trusted OAuth identity.

    OAuth providers have already verified the email identity. If an existing
    password account uses the same email, link the provider instead of creating
    a second account, and activate the account so OAuth login works.
    """
    db = get_db()
    email = email.strip().lower()

    user = db.users.find_one({"email": email})
    if user:
        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "name": name or user.get("name", ""),
                "oauth_provider": provider,
                "oauth_provider_id": str(provider_id),
                "auth_provider": provider,
                "email_verified": True,
                "is_active": True,
                "updated_at": now(),
            }},
        )
        linked = db.users.find_one({"_id": user["_id"]})
        logger.info(
            "OAUTH_USER_LINKED | provider=%s | user_id=%s | email=%s",
            provider,
            linked.get("_id"),
            mask_email(email),
        )
        return linked

    user = {
        "_id": uuid.uuid4().hex,
        "name": name or email.split("@")[0],
        "email": email,
        "password_hash": "",
        "role": "student",
        "is_active": True,
        "email_verified": True,
        "auth_provider": provider,
        "oauth_provider": provider,
        "oauth_provider_id": str(provider_id),
        "created_at": now(),
        "updated_at": now(),
    }
    db.users.insert_one(user)
    logger.info(
        "OAUTH_USER_CREATED | provider=%s | user_id=%s | email=%s",
        provider,
        user.get("_id"),
        mask_email(email),
    )
    return user


@router.get("/{provider}/start")
def oauth_start(request: Request, provider: str, redirect_uri: str):
    s = get_settings()
    provider = provider.lower()
    logger.info("OAUTH_START | provider=%s | redirect_uri=%s | configured_frontend=%s", provider, redirect_uri, s.frontend_web_url)
    redirect_uri = validate_oauth_redirect(redirect_uri)
    state = oauth_state(provider, redirect_uri)
    callback_uri = provider_callback_uri(request, provider)
    get_db().oauth_states.update_one({"_id": state}, {"$set": {"provider_callback_uri": callback_uri}})

    if provider == "google":
        if not s.google_client_id:
            raise HTTPException(503, "Google OAuth is not configured")
        params = urlencode({
            "client_id": s.google_client_id,
            "redirect_uri": callback_uri,
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
            "redirect_uri": callback_uri,
            "scope": "read:user user:email",
            "state": state,
        })
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")

    raise HTTPException(404, "Unsupported OAuth provider")


@router.get("/{provider}/callback")
def oauth_callback(request: Request, provider: str, code: str, state: str):
    s = get_settings()
    provider = provider.lower()
    logger.info(
        "OAUTH_CALLBACK_START | provider=%s | state_present=%s | code_present=%s",
        provider,
        bool(state),
        bool(code),
    )
    row = get_oauth_state(provider, state)
    callback_uri = row.get("provider_callback_uri") or provider_callback_uri(request, provider)
    logger.info("OAUTH_STATE_VALIDATED | provider=%s | callback_uri=%s", provider, callback_uri)

    if provider == "google":
        if not s.google_client_id or not s.google_client_secret:
            raise HTTPException(503, "Google OAuth is not configured")
        token_response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": callback_uri,
            "grant_type": "authorization_code",
        }, timeout=20)
        if not token_response.ok:
            logger.error(
                "OAUTH_TOKEN_EXCHANGE_FAILED | provider=google | status=%s",
                token_response.status_code,
            )
            raise HTTPException(400, "Google authorization failed")
        logger.info("OAUTH_TOKEN_EXCHANGE_SUCCESS | provider=google")
        access = token_response.json().get("access_token")
        profile = requests.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access}"}, timeout=20)
        if not profile.ok:
            logger.error(
                "OAUTH_PROFILE_FAILED | provider=google | status=%s",
                profile.status_code,
            )
            raise HTTPException(400, "Could not read Google profile")
        p = profile.json()
        logger.info(
            "OAUTH_PROFILE_RECEIVED | provider=google | email=%s",
            mask_email(p.get("email", "")),
        )
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
            "redirect_uri": callback_uri,
        }, headers={"Accept": "application/json"}, timeout=20)
        if not token_response.ok:
            logger.error(
                "OAUTH_TOKEN_EXCHANGE_FAILED | provider=github | status=%s",
                token_response.status_code,
            )
            raise HTTPException(400, "GitHub authorization failed")
        logger.info("OAUTH_TOKEN_EXCHANGE_SUCCESS | provider=github")
        access = token_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
        profile = requests.get("https://api.github.com/user", headers=headers, timeout=20)
        if not profile.ok:
            logger.error(
                "OAUTH_PROFILE_FAILED | provider=github | status=%s",
                profile.status_code,
            )
            raise HTTPException(400, "Could not read GitHub profile")
        p = profile.json()
        logger.info(
            "OAUTH_PROFILE_RECEIVED | provider=github | email=%s",
            mask_email(p.get("email", "")),
        )
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
    logger.info(
        "OAUTH_CALLBACK_SUCCESS | provider=%s | user_id=%s | redirect_uri=%s",
        provider,
        user.get("_id"),
        redirect_uri,
    )
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        f"{redirect_uri}{sep}{urlencode({'oauth_token': token})}"
    )
