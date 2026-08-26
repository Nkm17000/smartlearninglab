# Smart Learning Lab — Final Bulk Content Release — 2026-08-26

## Fixed root cause

The backend contained two competing bulk quiz implementations. `app/main.py` included `admin.router` before `bulk.router`, while `admin.py` also exposed a `/bulk/quiz` route. This made route behavior dependent on router order and could send requests to an older validator. The duplicate implementation has been removed from `admin.py`. The canonical implementation is now in `app/api/bulk.py`.

The frontend also had a separate batch validator that only accepted:

```json
"question": "...",
"options": ["A", "B", "C", "D"]
```

It rejected the bilingual object form before the request reached the backend. The shared frontend formatter now accepts both simple and bilingual formats and normalizes them before upload.

## Category / subcategory UX

- Global `Select all` selects every category and every subcategory.
- `Select subcategories` selects every subcategory under currently selected categories.
- `Clear all` removes the complete selection.
- Each category has its own `Select all` / `Clear all` for its subcategories.
- Individual categories and subcategories remain clickable, so an admin can select everything and then deselect specific items.
- The UI displays category and subcategory counts.

The same picker is used by the Bulk Quiz and PDF → Course tabs.

## Quiz JSON formats

Supported:

1. Simple single-language: `question` string + `options` array.
2. Bilingual: `question.english/hindi` + `options.english/hindi`.
3. Legacy bilingual: `question_hindi`, `options_hindi`, `explanation_hindi`.
4. Paired options: `options_bilingual`.

Every MCQ has exactly four English options. Bilingual content must have exactly four Hindi options as well.

## Samples

See:

- `samples/BULK_QUIZ_SIMPLE_SAMPLE.json`
- `samples/BULK_QUIZ_BILINGUAL_SAMPLE.json`
- `samples/BULK_QUIZ_LEGACY_BILINGUAL_SAMPLE.json`
- `samples/BULK_QUIZ_OPTIONS_BILINGUAL_SAMPLE.json`
- `BULK_UPLOAD_FORMAT_FINAL.md`

The Admin Bulk Content screen also provides Load/Download sample actions.

## Tests performed

- Python compile check for modified backend modules: passed.
- Frontend shared quiz formatter syntax check with Node: passed.
- Simple quiz validation: passed.
- New bilingual object format: passed.
- Legacy bilingual format: passed.
- `options_bilingual` format: passed.
- Incorrect Hindi option count: rejected.
- Incorrect simple option count: rejected.
- Batch source indexing: passed.
- Taxonomy payload mapping: passed.
- Duplicate `/bulk/quiz` implementation in `admin.py`: removed.
- Canonical `/admin/bulk/quiz`, `/admin/bulk/quiz-batch`, and `/admin/bulk/course-pdf` routes remain in `app/api/bulk.py`.

A complete browser/Render deployment test still requires the production environment and MongoDB/R2 credentials; those credentials are not part of this source package.
