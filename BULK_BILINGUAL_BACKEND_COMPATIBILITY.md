# Bulk Bilingual Backend Compatibility

The backend accepts both the new bilingual object shape and legacy bilingual fields.

Supported question options:
- `options: ["A", "B", "C", "D"]`
- `options: {"english": [...], "hindi": [...]}`
- `options` + `options_hindi`
- `options_bilingual`

The `/api/v1/admin/bulk/quiz-batch` endpoint validates and normalizes all of these shapes and preserves English/Hindi fields in MongoDB.
