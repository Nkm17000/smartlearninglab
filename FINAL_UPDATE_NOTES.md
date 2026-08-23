# Smart Learning Lab — Final BE Update

## Fixes
- Published quizzes are now independently openable. A stale or draft parent course no longer causes `/quizzes/{id}` or `/quizzes/{id}/questions` to return `Parent course not published`.
- Student quiz discovery lists published quizzes consistently with the detail endpoint.
- Mock Test adaptive endpoints are preserved.
- Gamification now has a real server-side game engine for Daily Challenge, Speed Quiz, Flashcard Battle, Match & Learn, Word Scramble and Boss Battle.
- Game sessions, answers, scores, XP, completion and badges are persisted in MongoDB.


## 2026-08-23 OAuth datetime fix
- Fixed OAuth state validation crash caused by comparing offset-naive and offset-aware datetimes.
- Added UTC normalization for existing MongoDB OAuth-state records.
- Added safe OAuth callback/state/token/profile logs without logging secrets or tokens.
- OAuth state creation already uses timezone-aware UTC via `now()`.
