# Bulk Upload Format

## Quiz JSON

The admin frontend accepts:

- one quiz object
- an array of quiz objects
- `{ "quizzes": [...] }`

Each quiz requires:

- `title`
- `subject`
- `questions`

Each question requires:

- `question`
- exactly 4 unique `options`
- `correct_answer` as zero-based index 0, 1, 2 or 3

Optional question fields:

- `difficulty`: `easy`, `medium`, or `hard`
- `marks`
- `negative_marks`
- `explanation`
- `tags`

Category and subcategory are selected in the admin UI and must not be added to individual quiz objects.

### Large files

There is no 500-quiz frontend limit. The frontend automatically sends the JSON in batches of 50 quizzes to:

`POST /api/v1/admin/bulk/quiz-batch`

Every batch response is shown in the UI. A failed quiz does not stop the other quizzes in the same batch.

## Course PDF

Course import is PDF-based, not a JSON course-content import.

Required:

- PDF file
- subject
- at least one category
- at least one subcategory

Optional:

- title (derived from filename/PDF when blank)
- level
- language

The API is:

`POST /api/v1/admin/bulk/course-pdf`

The original PDF is stored in R2 and the backend generates course modules and lessons from the PDF source.
