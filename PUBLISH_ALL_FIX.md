# Publish All Fix

Fixed the FastAPI route ordering for `POST /api/v1/admin/quizzes/publish-all`.

The dynamic route `/quizzes/{quiz_id}` was previously registered before the static `/quizzes/publish-all` route. FastAPI therefore interpreted `publish-all` as a quiz id for requests to Publish All.

The static `publish-all` route is now registered before `/quizzes/{quiz_id}`.

Frontend already calls:
`POST /api/v1/admin/quizzes/publish-all`

No FE API path change is required.
