# Final Auth Fixes

## Email confirmation
- Registration confirmation links are generated from the request environment.
- Local registration generates `http://127.0.0.1:8000/api/v1/auth/verify-email?...` when the registration request comes from localhost/127.0.0.1.
- Production registration generates the configured `BACKEND_PUBLIC_URL` link.
- `GET /api/v1/auth/verify-email` activates the account and redirects to the FE with `?verified=success`.
- Expiry timestamps are normalized to UTC to avoid naive/aware datetime errors.

## GitHub OAuth
- Local callback is derived from the local backend request.
- Production callback is derived from `BACKEND_PUBLIC_URL`.
- This prevents a stale `GITHUB_REDIRECT_URI` from producing a redirect mismatch.
- The exact production callback to register in GitHub is:
  `https://smartlearninglab.onrender.com/api/v1/auth/github/callback`
- For local GitHub testing, the GitHub OAuth App must register:
  `http://127.0.0.1:8000/api/v1/auth/github/callback`
  GitHub OAuth Apps normally have one callback URL, so use a separate GitHub OAuth App for local and production if both need to work simultaneously.
