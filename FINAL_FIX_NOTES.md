# Final Admin Fix

- Preserved the V4 backend and frontend.
- Fixed admin quiz filters for category, subject, subcategory, status, quiz type and question readiness.
- Added subject/subcategory handling to the backend admin quiz query.
- Fixed Publish All route ordering and retained validation.
- Added missing FE API methods for the Resource Library, course resources, lesson uploads, student library and R2 media downloads.
- Resource uploads use multipart/form-data without manually setting Content-Type, allowing the runtime boundary to be generated correctly.
- Admin Resource Library now connects to the existing backend /admin/library endpoints.
