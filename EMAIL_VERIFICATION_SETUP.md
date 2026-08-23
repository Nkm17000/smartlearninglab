# Student email confirmation

New password-based student registrations are created as `email_verified=false` and `is_active=false`.
The backend sends a confirmation email. The account becomes active only after the student clicks the confirmation link.

## Required environment variables

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true
EMAIL_VERIFICATION_HOURS=24
BACKEND_PUBLIC_URL=https://your-backend.example.com
FRONTEND_WEB_URL=https://your-frontend.example.com
```

For Gmail, use a Google **App Password**, not the normal account password.

For local testing, `BACKEND_PUBLIC_URL=http://127.0.0.1:8000` works when the email is opened on the same computer. For a real student/mobile deployment, use the publicly reachable HTTPS backend URL.

## Registration flow

1. Student submits name, email and password.
2. Backend creates a pending student account.
3. Backend sends the confirmation email.
4. Student clicks the link.
5. Backend verifies the token, sets `email_verified=true` and `is_active=true`, then redirects to the frontend.
6. Student can sign in.

If the student has not confirmed the email, login returns HTTP 403 and the FE provides **Resend confirmation email**.
