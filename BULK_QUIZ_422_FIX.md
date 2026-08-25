# Bulk Quiz 422 Fix

## Root cause
The POST `/api/v1/admin/bulk/quiz` handler previously declared `data` without a FastAPI `Body(...)` declaration. FastAPI therefore interpreted `data` as a required query parameter instead of the JSON request body. The frontend correctly sent JSON, but FastAPI rejected the request with HTTP 422.

## Fix
The handler now explicitly declares the JSON payload as the request body:

`def bulk_quiz(data: object = Body(...), user=Depends(admin_user))`

No frontend API URL, existing endpoint, authentication, quiz schema, PDF-to-course workflow, or other routes were changed.

## Regression checks
- Attached 18-topic English JSON parsed successfully.
- 18 quizzes validated.
- 180 questions validated.
- 10 questions per quiz.
- Single quiz object validated.
- `{ "quizzes": [...] }` wrapper validated.
- A/B/C/D answer normalization validated.
- Python source compilation completed successfully.
