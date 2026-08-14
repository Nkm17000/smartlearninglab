# Smart Learning Lab Backend

FastAPI + PyMongo backend for the Smart Learning Lab competitive-exam preparation app.

## Main features

- JWT authentication
- User profiles and selected exams
- Exams, subjects, topics, courses and lessons
- Question bank and PYQs
- Practice sets and mock tests
- Test attempts, answers and result analysis
- Student progress, mastery, mistakes and revision queue
- Study plans and daily goals
- Current affairs
- Bookmarks, favorites and personal notes
- Notifications
- Admin content management
- Basic AI conversation storage endpoint
- Health check
- MongoDB indexes
- Render-ready deployment

## Run locally

1. Create `.env` from `.env.example`.
2. Set `MONGODB_URI`.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Start:

```bash
uvicorn app.main:app --reload
```

API:
- http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Seed sample data

```bash
python seed.py
```

The seed script is safe to run repeatedly for the same sample records.

## Authentication

Register:

POST /api/v1/auth/register

Login:

POST /api/v1/auth/login

Use the returned access token as:

Authorization: Bearer <token>

## Important

The backend expects the MongoDB database `smart_learning_lab`. Collections may already exist; the application does not delete or recreate them.
