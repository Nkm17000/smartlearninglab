# Duplicate Email Registration Fix

Registration now rejects **any existing email** before creating a verification token or sending a confirmation email.

Behavior:
- Existing verified email -> HTTP 409: `Email already exists. Please login or use another email.`
- Existing unverified email -> HTTP 409: same message; use the existing resend-confirmation flow instead.
- New email -> account created as inactive/unverified and confirmation email is sent.

The lookup is case-insensitive, so `Student@Example.com` and `student@example.com` are treated as the same email.
