# Smart Learning Lab Backend - Admin/Student API

This version is aligned with the professional Expo FE.

## MongoDB

No separate `MONGODB_DB` variable is required. Put the database name directly in the URI:

```env
MONGODB_URI=mongodb+srv://username:password@smartstudylab.juh84i5.mongodb.net/smart_learning_lab
JWT_SECRET_KEY=your-long-random-secret
JWT_EXPIRE_MINUTES=1440
CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

## Run locally

```powershell
pip install -r requirements.txt
python seed_admin.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Swagger:

`http://127.0.0.1:8000/docs`

## Render

Environment variables:

- `MONGODB_URI`
- `JWT_SECRET_KEY`
- `JWT_EXPIRE_MINUTES=1440`
- `CORS_ORIGINS=*` (or your deployed FE origin)

Start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Main Admin workflow

```text
Admin Home
  -> Courses
  -> Manage Course
  -> Modules
  -> Lessons
  -> Question Bank
  -> Quizzes
  -> Publish
```

Important dedicated endpoints:

```text
GET    /api/v1/admin/courses
POST   /api/v1/admin/courses
GET    /api/v1/admin/courses/{course_id}
PUT    /api/v1/admin/courses/{course_id}
DELETE /api/v1/admin/courses/{course_id}

GET    /api/v1/admin/courses/{course_id}/modules
POST   /api/v1/admin/courses/{course_id}/modules

GET    /api/v1/admin/modules/{module_id}/lessons
POST   /api/v1/admin/modules/{module_id}/lessons

GET    /api/v1/admin/questions
POST   /api/v1/admin/questions
PUT    /api/v1/admin/questions/{question_id}
DELETE /api/v1/admin/questions/{question_id}

GET    /api/v1/admin/quizzes
POST   /api/v1/admin/quizzes
PUT    /api/v1/admin/quizzes/{quiz_id}
DELETE /api/v1/admin/quizzes/{quiz_id}

POST   /api/v1/admin/quizzes/{quiz_id}/questions
DELETE /api/v1/admin/quizzes/{quiz_id}/questions/{question_id}
```

The `GET /api/v1/admin/courses/{course_id}` endpoint is specifically included so the FE Manage Course button does not receive HTTP 405.
