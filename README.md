# Smart Learning Lab Backend v1

## What this backend provides

- Student/Admin authentication
- Role-based authorization
- Student dashboard
- Exams, subjects, topics, courses, lessons
- Question bank and practice
- Mock tests and submission
- Progress, mistakes, notes
- Current affairs
- AI conversation/message storage
- Admin dashboard
- Admin CRUD for learning content
- MongoDB Atlas

## Setup

1. Copy `.env.example` to `.env`.
2. Put your MongoDB Atlas URI with `/smart_learning_lab` at the end.
3. Set a strong JWT_SECRET_KEY.
4. Install dependencies:

   python -m pip install -r requirements.txt

5. Seed the database:

   python seed.py

The seed clears only application collections and recreates starter data.

## Demo accounts

Admin:
admin@smartlearninglab.com
ChangeMe123!

Student:
nitin@example.com
Password123!

Change these passwords before any real/public deployment.

## Run locally

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

Swagger:
http://127.0.0.1:8000/docs

Health:
http://127.0.0.1:8000/health

## Render

Start command:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

Environment variables:
MONGODB_URI
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
CORS_ORIGINS

Do not commit `.env` or real secrets.
