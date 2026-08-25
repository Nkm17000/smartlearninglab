# Student Portal Design Update

This update fixes the student `/home` and `/catalog/categories` API failures and aligns the Home, Courses and Quizzes screens with the supplied quiz-portal design.

## Backend fixes

- Added `GET /api/v1/catalog/categories`.
- Added `GET /api/v1/catalog/featured`.
- `/api/v1/home` now has all functions it calls.
- Added compatibility routes for course/module/lesson discovery used by the FE.
- Course filtering supports `categories[]`, legacy `category`, `exam`, `subject`, level and language.
- Student course listing defaults to all published courses; the FE explicitly sends `free_only=false`.
- Quiz completion remains shared by `subject + title` using `quiz_group_key`.
- Legacy scalar `category` is retained.

## MongoDB

Run `MONGO_STUDENT_PORTAL_DESIGN_MIGRATION.js` once. It adds/normalizes:

- `courses.categories` (array)
- `courses.subject`
- `quizzes.categories` (array)
- `quizzes.subject`
- `quizzes.quiz_group_key`

It also creates the indexes required for category/subject filtering and cross-exam completion.

No existing collection is deleted.

## Frontend

Updated only the student Home, Courses and Quizzes screens. Existing course detail, lesson, quiz attempt, authentication, study assistance, flashcards, admin and other routes remain unchanged.
