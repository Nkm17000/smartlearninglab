# Smart Learning Lab - Final Reliability Fix

## Recording-derived failures fixed

1. Admin Quiz Delete on the web portal
   - Web confirmation used `Alert.alert`, which is unreliable for this web target.
   - Replaced web confirmation with `window.confirm`.
   - Backend delete now verifies the quiz, removes the quiz, removes orphaned owned questions, removes attempts, and invalidates quiz caches.

2. Student quiz could not be submitted in the middle
   - The UI only exposed submit on the final question and blocked submission when every question was not answered.
   - Submission is now allowed at any question.
   - Unanswered questions are graded as unanswered/no marks.
   - Active attempt is stored server-side.
   - Answers and current question are autosaved.
   - Refresh/navigation resumes the active attempt.

3. Adaptive Mock Test had the same limitation
   - Submit is available before the final question.
   - Answers/current position are autosaved.
   - Active mock test is restored after refresh/navigation.
   - Server grades from the stored question IDs and answer key.

4. Admin Course creation returned HTTP 500
   - Course creation now normalizes taxonomy consistently.
   - Missing taxonomy can use a subject-safe default mapping for backward-compatible clients.
   - Duplicate-key failures are returned as HTTP 409 instead of opaque HTTP 500.
   - Course cache/dashboard cache is invalidated after create/update/delete.

5. Admin Manual Quiz creation
   - Manual quiz taxonomy handling now uses the same compatibility path as course creation.
   - Draft creation invalidates admin/student quiz caches.

6. Admin Resource Library file upload returned HTTP 422
   - Added a browser-native File picker for the web build.
   - The original File object is passed to multipart FormData instead of unnecessarily reconstructing it from a blob URL.
   - Backend accepts both `file` and legacy `upload` multipart field names.

7. Course/Lesson Resource PDF/file upload
   - Same cross-platform file picker and multipart fix.
   - Course resource upload remains stored in R2 with metadata in MongoDB.

8. Bulk PDF -> Course failed with:
   `Unknown category '["computer"]'. Create it in Admin -> Taxonomy first.`
   - Root cause: frontend encoded taxonomy arrays as JSON strings in multipart FormData while backend expected a comma-separated/list value.
   - Frontend now sends arrays as comma-separated multipart values.
   - Backend accepts JSON-array strings, comma-separated strings, and real arrays for backward compatibility.

9. Student Courses/Quizzes route separation
   - Explicit student `courses` and `quizzes` routes are registered in AppNavigator.
   - They no longer fall through to the Home screen.

## Verification performed

- Python `compileall` over the backend application: PASS.
- Python `py_compile` for modified backend modules: PASS.
- Node syntax check for `src/services/api.js`: PASS.
- Node syntax check for `src/services/filePicker.js`: PASS.
- Static scan of frontend `api.*` usages: no undefined API method usages found (ignoring exported helpers/constants and comments).
- Backend route scan completed. Duplicate route definitions found only in legacy `app/routers/*` files that are not included by the active `app/main.py`; active application imports `app.api.*` routers.

## E2E limitation

The attached recording demonstrates the deployed Cloudflare Pages application and Cloud Run API. This environment does not have the production admin credentials/database access required to execute destructive production CRUD/upload tests against that deployment. The release therefore includes code-level fixes and static verification, but production smoke tests must be executed after deployment with a real admin/student account.

10. Taxonomy parallel-array MongoDB index regression
   - Removed the unsafe `is_published + category_ids + subcategory_ids + subject` compound index shape.
   - Backend startup now repairs an already-deployed database automatically.
   - Added `MONGO_TAXONOMY_INDEX_REPAIR.js` as a manual fallback.
   - Added `TAXONOMY_INDEX_FIX_FINAL.md` with deployment details.
