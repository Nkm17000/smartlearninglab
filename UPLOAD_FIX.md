# Upload Endpoint

The `/api/v1/admin/bulk/course-pdf` endpoint already correctly expects:

- `file: UploadFile`
- `title: Form(...)`
- `category: Form(...)`
- `level: Form(...)`
- `language: Form(...)`

The observed 422 was caused by the frontend sending `[object Object]` for the `file` multipart part on web, not by the uploaded Java PDF. The backend is kept strict so malformed uploads are rejected clearly.

Required dependency: `python-multipart`.
