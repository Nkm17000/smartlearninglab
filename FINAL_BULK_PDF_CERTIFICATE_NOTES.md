# Final Bulk PDF + Certificate Integration

FastAPI/Python backend (not a Java JAR).

Features:
- Admin-only PDF course import: POST /api/v1/admin/bulk/course-pdf
- Admin-only PDF quiz import: POST /api/v1/admin/bulk/quiz-pdf
- Student certificates: GET /api/v1/certificates
- Student certificate issue after 100% course completion
- Student certificate PDF: GET /api/v1/certificates/{certificate_id}/pdf

Required environment variable for AI PDF import: GROQ_API_KEY.
