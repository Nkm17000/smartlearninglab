# Smart Learning Lab – Final Platform

This release includes the complete free-learning platform foundation:

- Student registration/login
- Forgot/reset password email flow
- Google/GitHub OAuth hooks
- Root admin and role-based staff management
- Course → topics → lessons → quizzes → questions
- Enrollment and learning progress
- Course search and discovery
- Test series and quiz attempts
- Student analytics, XP, levels and streaks
- Leaderboard and badges
- Bookmarks, notes and course reviews
- Notifications
- Course completion certificates + PDF endpoint
- Admin dashboard and platform analytics
- AI Tutor/conversation APIs from the existing project

## Environment

`MONGODB_URI` must include the database name. No separate MongoDB database parameter is required.

See `.env.example` for SMTP and OAuth settings.

## Run

```powershell
pip install -r requirements.txt
python seed_admin.py
python seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
