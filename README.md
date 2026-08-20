# Smart Learning Lab - Professional Backend v2

This backend is designed for the simplified professional Admin Portal:

**Create Course → Add Modules → Add Lessons → Question Bank → Create Quiz → Publish**

It keeps the existing learning endpoints and generic admin CRUD for compatibility, while adding clearer admin aliases for modules, lessons and quiz questions.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the real MongoDB URI and JWT secret.

Start:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/docs`.

## Render

Build:

```text
pip install -r requirements.txt
```

Start:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set `MONGODB_URI`, `MONGODB_DB`, `JWT_SECRET_KEY`, and `CORS_ORIGINS` in Render Environment Variables.

## Admin workflow endpoints

- `GET/POST /api/v1/admin/courses`
- `GET/POST /api/v1/admin/courses/{course_id}/modules`
- `GET/POST /api/v1/admin/modules/{module_id}/lessons`
- `GET/POST/PUT/DELETE /api/v1/admin/questions...`
- `GET/POST/PUT/DELETE /api/v1/admin/quizzes...`
- `POST /api/v1/admin/quizzes/{quiz_id}/questions`
- `DELETE /api/v1/admin/quizzes/{quiz_id}/questions/{question_id}`

All Admin endpoints require a bearer token for a user whose role is `admin`.

## Existing API compatibility

The previous endpoints remain available, including `/api/v1/auth/*`, `/api/v1/exams`, `/api/v1/subjects`, `/api/v1/topics`, `/api/v1/courses`, `/api/v1/lessons`, `/api/v1/questions`, `/api/v1/mock-tests`, `/api/v1/dashboard`, `/api/v1/progress`, `/api/v1/notes`, and `/api/v1/ai/*`.
