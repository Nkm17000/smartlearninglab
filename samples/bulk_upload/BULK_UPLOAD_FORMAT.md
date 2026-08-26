# Bulk quiz JSON format

The admin Bulk Content screen accepts all three quiz formats below.

## 1. Single language

`question` is a string and `options` is an array of exactly four strings.

## 2. Bilingual

`question` is `{ "english": "...", "hindi": "..." }` and `options` is `{ "english": [...], "hindi": [...] }`. Both arrays must contain exactly four options. The same `correct_answer` index applies to both languages.

## 3. Legacy bilingual

Use `question_hindi` and `options_hindi` alongside the normal single-language fields.

`correct_answer` may be 0, 1, 2, 3, A, B, C, D, or exact option text.

For large files, the frontend reads and processes the JSON outside the main UI where Web Workers are available and sends at most 50 quizzes per request to `POST /api/v1/admin/bulk/quiz-batch`.

Course upload remains PDF based. Required metadata: PDF, subject, one or more categories and subcategories. Title is optional; level and language are optional.
