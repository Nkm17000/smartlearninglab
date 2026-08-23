# SmartLearningLab Performance Final

## Main production changes
- Student Home uses `/api/v1/home` as a single initial request.
- Course overview returns course, modules, lessons, resources, progress, reviews and bookmark state in one response.
- Student lesson uses `/api/v1/lessons/{lesson_id}` as a single view payload.
- Quiz screen uses `/api/v1/quizzes/{quiz_id}/bundle` for metadata, questions and attempt state.
- My Learning uses `/api/v1/learning/summary`.
- Analytics uses `/api/v1/analytics/summary`.
- Personalized path batches quiz metadata instead of querying once per weak attempt.
- Results batch-load quiz metadata instead of one MongoDB query per attempt.
- Short TTL caches are used for user-changing data; longer TTLs are used for catalogue/reference data.
- Cache keys containing user-specific course state include the user ID to prevent cross-user cache leakage.
- MongoDB connection pooling remains enabled.
- R2 remains the binary storage layer; MongoDB stores metadata/references.

## Important
The in-process cache is intentionally short-lived and per-process. MongoDB remains the source of truth. If the Render service is scaled to multiple instances, use Redis for shared caching rather than relying on process-local cache.
