# Smart Learning Lab — Exam Category + Subject Taxonomy

## Canonical content fields

Courses and quizzes now support:

- `categories`: array of exam categories
- `category`: first category, retained for backward compatibility
- `subject`: learning subject
- Quizzes additionally use `quiz_group_key` to identify the same quiz across exam categories.

Example:

```json
{
  "title": "English Grammar - Noun",
  "categories": ["SSC", "Railway", "Banking"],
  "subject": "English"
}
```

A quiz completed under SSC is considered completed for another published copy when its `subject` and quiz title resolve to the same `quiz_group_key`.

## Supported exam categories

SSC, Railway, Banking, UPSC, Computer, Teaching, Defence, State Exams, General, English Spoken, Other.

## Subject examples

English, Hindi, Math, Reasoning, General Awareness, Current Affairs, Science, Physics, Chemistry, Biology, Computer, Java, Python, PHP, SQL, DBMS, Operating Systems, Networking, Spring Boot, Microservices, Aptitude, Other.

## Backward compatibility

Old records containing only `category: "SSC"` are still returned correctly. The migration script adds `categories` and `subject` without deleting the legacy field.

Older bulk quiz JSON where `category: "English"` was used as the subject is also accepted. The importer treats that as `subject: "English"` and uses the selected/default exam categories.

## API filters

Admin:

- `GET /api/v1/admin/courses?category=SSC&subject=English&status=published`
- `GET /api/v1/admin/quizzes?category=SSC&subject=English&status=published`
- `GET /api/v1/admin/quiz-categories`

Student:

- `GET /api/v1/courses?category=SSC&subject=English`
- `GET /api/v1/quizzes?category=SSC&subject=English`

## Completion rule

Completion is based on the quiz group identity, not the exam category. If the student submits the English Grammar - Noun quiz in SSC, the same English Grammar - Noun quiz in Railway/Banking/UPSC is returned with `is_completed: true`.
