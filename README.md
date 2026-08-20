# Smart Learning Lab — Adda-style learning platform backend

This version uses the uploaded Adda247-style workflow as a product/design reference: exam/category discovery, featured courses, structured course curriculum, test series, resources and learner progress. It does not copy Adda247 branding/assets.

## Run locally

```powershell
pip install -r requirements.txt
python seed_admin.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Swagger: http://127.0.0.1:8000/docs

## Environment

```env
MONGODB_URI=mongodb+srv://username:password@smartstudylab.juh84i5.mongodb.net/smart_learning_lab
JWT_SECRET_KEY=change-this-to-a-long-random-secret
JWT_EXPIRE_MINUTES=1440
CORS_ORIGINS=*
```

No separate MONGODB_DB setting is required. The database is taken from the MongoDB URI.

## Main learner APIs

- `GET /api/v1/dashboard`
- `GET /api/v1/catalog/categories`
- `GET /api/v1/catalog/featured`
- `GET /api/v1/courses?search=&category=&level=&language=`
- `GET /api/v1/courses/{course_id}`
- `GET /api/v1/courses/{course_id}/overview`
- `GET /api/v1/courses/{course_id}/modules`
- `GET /api/v1/quizzes`
- `GET /api/v1/quizzes/{quiz_id}/questions`
- `POST /api/v1/lessons/{lesson_id}/complete`
- `GET /api/v1/courses/{course_id}/progress`
- `POST /api/v1/quizzes/{quiz_id}/start`
- `POST /api/v1/quizzes/{quiz_id}/submit`

## Admin content model

Course -> Topics/Modules -> Lessons -> Quizzes -> Questions.

Courses also support exam/category, instructor, language, tags, free flag, video/PDF/mock-test counts, featured flag and learning objectives. All of these can be managed from the admin portal; no direct MongoDB editing is required.

## Authentication features
- Student registration: `POST /api/v1/auth/register`
- Forgot password email: `POST /api/v1/auth/forgot-password`
- Reset password: `POST /api/v1/auth/reset-password`
- Google OAuth: `/api/v1/auth/google/start` and callback
- GitHub OAuth: `/api/v1/auth/github/start` and callback
- Root Admin can create staff roles: admin, content_admin, instructor, support_admin.

Configure SMTP and OAuth credentials in `.env` before enabling those features.

## Google / GitHub OAuth setup
1. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`.
2. Set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `GITHUB_REDIRECT_URI`.
3. For local development, use the callback URLs shown in the FE README.
4. In production, use the public Render API callback URLs and set `FRONTEND_WEB_URL` to the deployed FE URL.

OAuth users are created as `student` accounts. Existing users with the same email are linked to the social provider.

## Password reset email
Configure SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`). Gmail requires an App Password when 2-step verification is enabled.
