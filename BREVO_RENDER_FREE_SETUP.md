# Brevo + Render Free Email Setup

The backend now prefers Brevo transactional email over HTTPS when `BREVO_API_KEY` is set.
Registration confirmation, resend confirmation, and forgot-password all call the same `send_email()` function.

## Render backend variables

Set these on the Render backend service:

- `BREVO_API_KEY` = your Brevo API key (do not commit it)
- `BREVO_SENDER_EMAIL` = a sender verified in Brevo
- `BREVO_SENDER_NAME` = `Smart Learning Lab`
- `BREVO_API_URL` = `https://api.brevo.com/v3/smtp/email`

Keep the existing MongoDB/JWT/OAuth variables. SMTP variables are no longer required on Render.

## Why this fixes the Render error

Render Free cannot reach Gmail SMTP on port 587. Brevo's transactional API uses HTTPS, so the backend sends the email to `https://api.brevo.com/v3/smtp/email` instead.

## Important

The sender email must be registered/verified in Brevo before real emails can be sent.

## Frontend

The Expo web frontend uses:
`https://smartlearninglab.onrender.com/api/v1`

The auth request timeout is 90 seconds so Render cold starts do not cause a false timeout.
