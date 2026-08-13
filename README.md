# Smart Learning Lab Backend

FastAPI + MongoDB backend for the Smart Learning Lab Android application.

## Database

The application uses the existing MongoDB database:

smart_learning_lab

Expected collections:

users
courses
subjects
lessons
videos
quizzes
questions
quiz_attempts
student_progress
bookmarks
achievements
notifications

## Setup

Create a virtual environment:

python -m venv .venv

Windows:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Copy .env.example to .env and set the MongoDB Atlas connection string.

Run:

uvicorn app.main:app --reload

Swagger:

http://localhost:8000/docs

Welcome:

http://localhost:8000/

Health:

http://localhost:8000/api/health

## Main API groups

POST /api/auth/register
POST /api/auth/login

GET /api/users/me

GET /api/courses
GET /api/courses/{course_id}
POST /api/courses

GET /api/subjects
GET /api/subjects/{item_id}

GET /api/lessons
GET /api/lessons/{lesson_id}

GET /api/videos
GET /api/videos/{item_id}

GET /api/quizzes/{quiz_id}
POST /api/quizzes/{quiz_id}/submit

GET /api/progress/{course_id}
POST /api/progress/{course_id}/lessons

GET /api/bookmarks
POST /api/bookmarks

GET /api/achievements
POST /api/achievements

GET /api/notifications
POST /api/notifications

## Important

The .env file is ignored by Git. Do not commit MongoDB passwords or JWT secrets.

Quiz questions returned to the Android client do not include correct_answer before submission.
