# Smart Learning Lab API - MVP endpoints

## System
GET /
GET /health
GET /docs

## Auth
POST /api/v1/auth/register
POST /api/v1/auth/login
GET /api/v1/auth/me
PUT /api/v1/auth/me

## Exams
GET /api/v1/exams
GET /api/v1/exams/{exam_id}
GET /api/v1/exams/{exam_id}/subjects
GET /api/v1/exams/{exam_id}/syllabus
GET /api/v1/exams/{exam_id}/notifications
GET /api/v1/exams/me/profiles
POST /api/v1/exams/{exam_id}/profile

## Learning
GET /api/v1/learning/categories
GET /api/v1/learning/subjects
GET /api/v1/learning/subjects/{subject_id}/topics
GET /api/v1/learning/topics/{topic_id}
GET /api/v1/learning/courses
GET /api/v1/learning/courses/{course_id}
GET /api/v1/learning/lessons/{lesson_id}
POST /api/v1/learning/lessons/{lesson_id}/complete

## Questions
GET /api/v1/questions
GET /api/v1/questions/{question_id}
GET /api/v1/questions/{question_id}/explanation
POST /api/v1/questions/{question_id}/bookmark
DELETE /api/v1/questions/{question_id}/bookmark

## Tests
GET /api/v1/tests/mock
GET /api/v1/tests/mock/{mock_id}
POST /api/v1/tests/mock/{mock_id}/start
POST /api/v1/tests/attempt/{attempt_id}/answer
POST /api/v1/tests/attempt/{attempt_id}/submit
GET /api/v1/tests/attempt/{attempt_id}/result
GET /api/v1/tests/attempts/me

## Progress
GET /api/v1/progress/dashboard
POST /api/v1/progress/mastery
POST /api/v1/progress/mistakes/{question_id}
GET /api/v1/progress/mistakes
GET /api/v1/progress/revision

## Current Affairs
GET /api/v1/current-affairs
GET /api/v1/current-affairs/categories
GET /api/v1/current-affairs/monthly/{month}

## Personal
GET /api/v1/me/bookmarks
GET /api/v1/me/favorites
POST /api/v1/me/notes
GET /api/v1/me/notes
POST /api/v1/me/goals
GET /api/v1/me/goals

## Notifications
GET /api/v1/notifications
POST /api/v1/notifications/{notification_id}/read

## AI storage
POST /api/v1/ai/conversations
GET /api/v1/ai/conversations
POST /api/v1/ai/messages
GET /api/v1/ai/conversations/{conversation_id}/messages

## Admin
GET /api/v1/admin/dashboard
POST /api/v1/admin/exams
POST /api/v1/admin/subjects
POST /api/v1/admin/topics
POST /api/v1/admin/courses
POST /api/v1/admin/lessons
POST /api/v1/admin/questions
GET /api/v1/admin/questions
DELETE /api/v1/admin/questions/{question_id}
