# Bulk Quiz Topic Import — Final

## Supported input

The admin Bulk Content Studio accepts:

1. One quiz object
2. An array of quiz objects
3. `{ "quizzes": [ ... ] }`
4. A `.json` file containing any of the above (a `.txt` file containing valid JSON is also accepted)

## Import rule

**One quiz object becomes one quiz draft.**

If an upload contains 18 topic objects, the backend creates 18 separate quiz drafts. Questions are never combined across topic objects.

Example:

```json
[
  { "title": "English Grammar - Noun", "category": "English", "questions": [] },
  { "title": "English Grammar - Pronoun", "category": "English", "questions": [] }
]
```

This creates two quiz drafts: Noun and Pronoun.

## Validation

Before any MongoDB write, the complete upload is validated for:

- quiz title
- duplicate titles inside the same upload
- questions
- options
- correct answers
- duration
- passing percentage
- maximum attempts
- quiz category

`correct_answer` supports zero-based indexes, letters such as `A/B/C/D`, numeric strings, and exact option text.

All imported quizzes remain drafts until reviewed and published through the existing admin quiz workflow.

## Admin UI

The Bulk Content Studio is branded as **Nitin Mittal Innovation** and does not display admin credentials.
