# Smart Learning Lab — MongoDB Backend

FastAPI backend for the React Native + Web Smart Learning Lab application.

MongoDB is the source of truth. The API reads the existing collections directly:
users, courses, subjects, lessons, videos, quizzes, questions,
quiz_attempts, student_progress, bookmarks, achievements, notifications.

## 1. Configure
Create `.env` from `.env.example`.

Example:
MONGODB_URL=mongodb+srv://...
MONGODB_DATABASE=smartlearninglab
JWT_SECRET_KEY=use-a-long-random-secret

## 2. Install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

## 3. Run
uvicorn app.main:app --reload

Swagger:
http://127.0.0.1:8000/docs

## 4. Optional sample data
`scripts/seed_sample.py` only inserts sample documents when a collection has no
documents. It does not delete your existing MongoDB data.

python scripts/seed_sample.py

Demo accounts created by the sample script:
student@smartlearninglab.com / Student@12345
admin@smartlearninglab.com / Admin@12345

## Important
Do NOT put MONGODB_URI in the React Native app. Only the FastAPI backend connects
to MongoDB.

For Render, set MONGODB_URI, MONGODB_DATABASE and JWT_SECRET as environment
variables in the Render service.
