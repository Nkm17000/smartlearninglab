# Study Assistance Backend

Added two authenticated student endpoints:

- `GET /api/v1/study-assistance`
- `GET /api/v1/study-assistance/search?q=...&limit=...`

The implementation uses existing MongoDB learning data and the existing in-process TTL cache. It does not call an AI provider or add a new database/service.

The existing AI/admin endpoints remain untouched for backward compatibility, but the student Study Assistance portal does not call them.
