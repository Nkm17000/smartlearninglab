# Google + GitHub OAuth — Final Setup

The backend already exposes:
- GET /api/v1/auth/google/start
- GET /api/v1/auth/google/callback
- GET /api/v1/auth/github/start
- GET /api/v1/auth/github/callback
- GET /api/v1/auth/me?token=<jwt>

The FE now:
- starts OAuth from the login screen
- handles the returned `oauth_token` on Expo Web
- handles `smartlearninglab://oauth?oauth_token=...` on mobile
- stores the returned user/session
- navigates into the existing new-design application
- displays success/error notifications

## Local `.env`

```env
FRONTEND_WEB_URL=http://localhost:8081
BACKEND_PUBLIC_URL=http://127.0.0.1:8000

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/google/callback

GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/github/callback
```

## Google Cloud

Register exactly:

`http://127.0.0.1:8000/api/v1/auth/google/callback`

as the authorized redirect URI.

## GitHub

Register exactly:

`http://127.0.0.1:8000/api/v1/auth/github/callback`

as the callback URL.

## Important

The provider callback URL is the BACKEND URL. It is not the Expo URL.

The Expo Web URL is:

`http://localhost:8081/`

After OAuth succeeds, the backend redirects there with a short-lived application JWT in the query string. The FE immediately exchanges that token for the user payload and removes it from the browser URL.

For production, use HTTPS backend callback URLs and register those exact URLs with Google and GitHub.
