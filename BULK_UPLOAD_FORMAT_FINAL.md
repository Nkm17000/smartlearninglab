# Bulk Quiz Upload Format — Final

## Simple
`question` is a string and `options` is an array of exactly four strings.

## Bilingual
`question` is `{ "english": "...", "hindi": "..." }` and `options` is `{ "english": [...], "hindi": [...] }`. Both arrays contain exactly four options and the same `correct_answer` index applies to both.

## Legacy bilingual
`question_hindi`, `options_hindi`, and `explanation_hindi` are supported alongside the normal fields.

## Paired bilingual
`options_bilingual` accepts four `{ "english": "...", "hindi": "..." }` objects.

## Validation
- Exactly 4 English options for every MCQ.
- Exactly 4 Hindi options when bilingual fields are supplied.
- No empty or duplicate options.
- `correct_answer`: 0–3, A–D, or exact option text.
- Categories/subcategories are selected once in Admin Bulk Content and applied to every uploaded item.
- Quiz uploads are processed in batches of 50.

## API
`POST /api/v1/admin/bulk/quiz-batch` accepts upload-level `category_ids`, `categories`, `subcategory_ids`, `subcategories`, and a `quizzes` array.
`POST /api/v1/admin/bulk/course-pdf` accepts the PDF plus the same taxonomy fields.

The duplicate legacy `/admin/bulk/quiz` route was removed from `app/api/admin.py`; the canonical bulk implementation is `app/api/bulk.py`. This prevents FastAPI route-order conflicts with stale validators.
