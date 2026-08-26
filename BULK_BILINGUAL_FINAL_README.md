# Smart Learning Lab - Bulk Quiz Bilingual Update

This package is the current BE/FE source with the bulk quiz importer updated to support:
- Single-language quiz JSON
- English + Hindi bilingual quiz JSON
- Legacy bilingual fields (`question_hindi`, `options_hindi`, `explanation_hindi`)
- Exactly four options
- 0-based or A/B/C/D answers
- Duplicate option/question validation
- Large JSON processing in batches of 50
- Per-batch progress and per-quiz failures
- Retry/idempotency protection
- Existing upload-level category/subcategory taxonomy

## FE

```bash
npm install
npm run check:api
npm run web
# production web build:
npm run build:web
```

Configure `.env` using `.env.example`.

## BE

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configure the environment using `.env.example`.

## Bulk endpoint

`POST /api/v1/admin/bulk/quiz-batch`

Maximum 50 quizzes per request.

## Samples

See `samples/bulk_upload/`.
