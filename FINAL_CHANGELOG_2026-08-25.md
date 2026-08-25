# Smart Learning Lab — Final Admin/Student Fixes — 25 Aug 2026

## Backend

- Removed the MongoDB parallel-array taxonomy index problem (`category_ids` + `subcategory_ids`).
- Added automatic taxonomy index repair during FastAPI startup.
- Updated the taxonomy migration so it never creates an unsafe two-array compound index.
- Added a manual `MONGO_TAXONOMY_INDEX_REPAIR.js` fallback.
- Fixed student lesson navigation ordering: topic order is now respected instead of MongoDB ObjectId order.
- Reworked gamification question selection so recent questions are excluded for the learner's last 8 runs of the same game and the remaining pool is randomized.
- Fixed gamification answer-key alignment so the answer key always belongs to the actual item shown to the student.
- Fixed MCQ correct-answer normalization for numeric, letter, and exact-option formats.
- Word Scramble now accepts only a single alphabetic English spelling word; phrases and punctuation are rejected.

## Frontend

- Fixed Admin Library multipart upload on web. The browser now sends the real `File`/`Blob` instead of a React Native `{uri,...}` object.
- Applied the same safe upload path to course resources, lesson resources, and PDF → AI Course uploads.
- Fixed Student Course Next/Previous navigation. `StudentLessonScreen` now supports the callbacks exposed by `AppNavigator`; clicking Next/Previous changes the route and loads the target lesson API payload.
- Refreshed Student Course UI with a richer course hero and dynamic course visual identity.
- Refreshed Student Quiz UI with stats, progress, question navigator, answer states, auto-save messaging, timer, and review layout.
- Refreshed Gamification question cards with rotating visual themes and English-specific Word Scramble wording.

## Validation

- Python source compiled successfully with `python -m compileall`.
- Changed JavaScript service/screen files passed `node --check` where applicable.
- A full Expo production build was not run because dependency installation (`npm ci`) exceeded the available execution window in this environment. No claim of a full production E2E build is made.
