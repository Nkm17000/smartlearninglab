# Smart Learning Lab — Final Platform Frontend

The frontend keeps the existing course/admin/student experience and adds:

- AI tutor grounded retrieval workflow
- AI speaking-practice screen
- watch/resource API support
- gamification API support
- email verification API support
- device-token API support
- richer test attempt APIs
- detailed admin analytics API support

## Start

```powershell
npm install
npx expo start -c
```

Set:

`EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1`

For a deployed backend, replace it with the deployed API base URL.

## AI Intelligence Upgrade

This version adds a new AI-first product layer:

- AI Personal Learning Coach
- AI-generated personalized quizzes
- AI Study Plan generator
- PDF to AI course blueprint and draft-course saving
- At-risk student detection for admins
- Career / skill roadmap
- AI mock interview and answer evaluation
- AI Course Health Checker
- Global semantic-style search across courses, lessons and questions
- Offline lesson-completion queue with server sync

### New routes

Student: `/api/v1/ai/coach`, `/api/v1/ai/personalized-quiz`, `/api/v1/ai/study-plan`, `/api/v1/career/roadmap`, `/api/v1/ai/mock-interview`, `/api/v1/ai/mock-interview/evaluate`, `/api/v1/search`, `/api/v1/offline/sync`

Admin: `/api/v1/admin/ai/course-from-pdf`, `/api/v1/admin/ai/course-from-pdf/save`, `/api/v1/admin/students/at-risk`, `/api/v1/admin/courses/{course_id}/health`

The mobile app now exposes **AI Studio** for students and **AI Intelligence** for admins.
