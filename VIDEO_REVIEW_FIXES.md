# Video review fixes

Based on the supplied full application recording:

- Several screens showed large loading panels or the generic crash screen when one secondary API call failed.
- The student home was too admin-like and did not prioritize continuation of learning.
- The navigation was visually dense.
- Empty states and loading states had too much unused whitespace.
- The previous pink-heavy palette was replaced with a modern education palette: indigo primary, cyan accent, amber highlights, dark navy text and a soft cool background.
- Student Home now prioritizes Continue Learning, quick stats, exam discovery, featured courses, test series and learning tools.
- Student Home, Course and Quiz screens tolerate non-critical endpoint failures using `Promise.allSettled`.
- Notes, Community, Flashcards and Personalized Learning now have retryable error states instead of silent/indefinite loading.
- API requests retry transient 502/503/504 failures once.
- The API response normalizer supports arrays, `items`, `data` and `results` envelopes.
- Backend `/api/v1/dashboard` now includes per-course progress metadata.
- Backend course overview now includes lesson resources from the `lesson_resources` collection.
