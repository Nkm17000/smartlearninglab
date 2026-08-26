
## 50-Quiz Batch Upload Update

The admin frontend now uses `POST /api/v1/admin/bulk/quiz-batch` for bulk quiz JSON imports. The endpoint accepts a maximum of 50 quizzes per request and returns created, skipped, and failed quiz counts plus per-quiz failures.

Large JSON files are split by the frontend into 50-quiz requests. A `bulk_upload_id` and `_bulk_source_index` make retried batches idempotent, so already-created items are reported as skipped instead of being duplicated.
