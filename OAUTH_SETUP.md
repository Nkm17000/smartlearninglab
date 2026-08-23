# Google / GitHub OAuth setup

## Local development

FastAPI callback URLs:

```text
Google: http://127.0.0.1:8000/api/v1/auth/google/callback
GitHub: http://127.0.0.1:8000/api/v1/auth/github/callback
```

FE redirect destination used by Expo Web:

```text
http://localhost:8081/
```

Set:

```env
BACKEND_PUBLIC_URL=http://127.0.0.1:8000
FRONTEND_WEB_URL=http://localhost:8081
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/google/callback
GITHUB_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/github/callback
```

If you open Expo Web as `http://127.0.0.1:8081`, the backend now accepts that local loopback variant too.

## Google Cloud

In the Google OAuth client, add the exact authorized redirect URI:

```text
http://127.0.0.1:8000/api/v1/auth/google/callback
```

Google requires the redirect URI used by the authorization-code flow to exactly match an authorized redirect URI.

## GitHub

In the GitHub OAuth App, set the Authorization callback URL to:

```text
http://127.0.0.1:8000/api/v1/auth/github/callback
```

GitHub also validates the callback URL against the registered callback URL.

For production, replace both callback URLs with the HTTPS backend callback URL and register that exact URL with each provider.
