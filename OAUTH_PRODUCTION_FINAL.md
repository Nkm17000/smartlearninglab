# Smart Learning Lab OAuth Production Configuration

Backend Render URL:
`https://smartlearninglab.onrender.com`

Google callback:
`https://smartlearninglab.onrender.com/api/v1/auth/google/callback`

GitHub callback:
`https://smartlearninglab.onrender.com/api/v1/auth/github/callback`

Set these Render environment variables (use your real values for secrets):

```env
BACKEND_PUBLIC_URL=https://smartlearninglab.onrender.com
FRONTEND_WEB_URL=https://YOUR-FRONTEND.onrender.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://smartlearninglab.onrender.com/api/v1/auth/google/callback
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=https://smartlearninglab.onrender.com/api/v1/auth/github/callback
```

The frontend OAuth start endpoint receives the current browser origin as the post-login destination. The backend validates that destination against `FRONTEND_WEB_URL` (or localhost during local development).
