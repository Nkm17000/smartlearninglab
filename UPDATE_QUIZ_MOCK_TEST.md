# Final BE update - Quiz + Mock Test

Changes:
- Publishing a quiz now also publishes its attached questions.
- Student quiz discovery filters out quizzes whose parent course/topic is not published.
- Quiz questions are returned in the quiz's question_ids order after the quiz is published, with answers hidden.
- Quiz submission grades against the quiz's attached question IDs.
- Adaptive/mock tests now create a server-side adaptive_attempts session.
- Mock-test submission grades from the server-side question records, fixing the previous zero/unavailable result issue.

No Mongo migration is required. The `adaptive_attempts` collection is created automatically when the first mock test is started.

Run:
`python -m pip install -r requirements.txt`
`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
