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
