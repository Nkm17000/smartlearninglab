# SmartLearningLab R2 Storage

Structured application data remains in MongoDB. Binary/heavy assets are stored in Cloudflare R2.

## MongoDB
Users, auth, courses, lessons, quizzes, flashcards, progress, enrollments, and other structured/user-specific data.

## R2
PDF, image, video, audio, document, ZIP, and other binary course/library resources. MongoDB stores `storage_key`, `media_id`, and metadata.

## Render environment
Set:
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME=smartlearninglab-storage`
- `R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (optional; backend builds it automatically)
- `R2_SIGNED_URL_EXPIRY=900`

Keep R2 secrets only in the backend/Render environment. Never put them in Expo.

`GET /api/v1/storage/health` (admin) verifies the connection. Existing course/lesson/library upload endpoints now store uploaded binary data in R2 while retaining metadata in MongoDB. Media access uses short-lived signed R2 URLs.
