# Student Registration / Email Confirmation

## Flow
1. Student submits registration.
2. Backend creates an inactive, unverified account.
3. Backend sends a Gmail SMTP confirmation link.
4. FE displays: "Please confirm on your mail for registration."
5. Student clicks the link.
6. Backend verifies the token, activates the account, and redirects to the FE.
7. FE displays registration completed and allows sign-in.

## Local environment

Backend `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-gmail@gmail.com
SMTP_USE_TLS=true
EMAIL_VERIFICATION_HOURS=24
BACKEND_PUBLIC_URL=http://127.0.0.1:8000
FRONTEND_WEB_URL=http://localhost:8081
LOG_LEVEL=INFO
LOG_DIR=logs
```

The Gmail password must be a Google App Password, not the normal Gmail password.

## Local run

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Useful log events

```text
AUTH_REGISTER_START
SMTP_SEND_START
SMTP_AUTH_SUCCESS
SMTP_SEND_SUCCESS
AUTH_REGISTER_SUCCESS
AUTH_RESEND_VERIFICATION_START
AUTH_RESEND_VERIFICATION_SUCCESS
AUTH_VERIFY_EMAIL_START
AUTH_VERIFY_EMAIL_SUCCESS
AUTH_LOGIN_SUCCESS
```

SMTP credentials and tokens are never logged.
