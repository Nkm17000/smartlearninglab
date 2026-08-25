# Final Taxonomy / Admin Reliability Fix

## Root cause
The taxonomy change added `category_ids` and `subcategory_ids` as arrays. A previous MongoDB migration created a compound index containing both arrays:

`is_published + category_ids + subcategory_ids + subject`

MongoDB rejects documents that populate both arrays with:

`Cannot index parallel arrays [subcategory_ids] [category_ids]`

This caused Admin course creation and PDF-to-course import to return HTTP 500.

## Permanent fix
- Application startup now detects and removes any course/quiz index containing both array fields.
- Safe single-array indexes are created instead.
- Safe filtered indexes use only one taxonomy array at a time.
- The migration script was corrected so the invalid index is never recreated.

## Library upload fix
The web frontend was constructing React-Native style `{uri, name, type}` objects directly in three upload methods. On web, the backend could receive no usable multipart file and returned HTTP 422.

All three methods now use the shared cross-platform upload helper, which preserves the browser `File` object and correctly sends multipart data:
- Admin Learning Library upload
- Course resource upload
- Lesson resource upload

## Deployment
Deploy the backend first, then the frontend. The backend startup repair automatically fixes the already-existing MongoDB index, so no manual MongoDB command is required.
