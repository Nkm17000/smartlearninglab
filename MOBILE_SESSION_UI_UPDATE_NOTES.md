# Smart Learning Lab – Backend Deployment Update

The backend application logic already returns HTTP 401 for invalid/expired JWTs through `app/core/security.py`. No destructive backend authentication rewrite was made.

The `.env.example` file was updated with the current production examples:

- Cloudflare Pages frontend
- Google Cloud Run backend
- Google OAuth callback
- GitHub OAuth callback
- CORS including the production frontend and local development origins

Set the actual values as Cloud Run environment variables; do not commit secrets.
