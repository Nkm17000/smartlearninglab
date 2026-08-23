# Performance cache policy

The backend uses a bounded in-process TTL cache. MongoDB remains the source of truth.

- Dashboard: 30 seconds per user
- Course catalogue/search: 60 seconds per user/query
- Categories/exams/levels: 15 minutes
- Featured courses/quizzes: 5 minutes
- Course overview: 5 minutes
- Quiz list: 60 seconds
- Personalized path: 2 minutes per user

The cache is deliberately short-lived because Render instances can restart and may be
scaled independently. No persistent learning data is stored in the cache.
