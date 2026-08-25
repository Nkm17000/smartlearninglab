# Bulk Quiz Topic Import — Upload-Level Taxonomy

## Supported input

The admin Bulk Content Studio accepts:

1. One quiz object
2. An array of quiz objects
3. `{ "quizzes": [ ... ] }`
4. A `.json` file containing any of the above (a `.txt` file containing valid JSON is also accepted)

## Import rule

**One quiz object becomes one quiz draft.**

If an upload contains 18 topic objects, the backend creates 18 separate quiz drafts. Questions are never combined across topic objects.

Category and subcategory are **not fields inside the quiz objects**. They are selected once in the Admin UI and applied to every quiz in that upload.

Example JSON:

```json
[
  { "title": "English Grammar - Noun", "subject": "English", "topic": "Noun", "questions": [] },
  { "title": "English Grammar - Pronoun", "subject": "English", "topic": "Pronoun", "questions": [] }
]
```

If the admin selects `SSC` + `Banking` and `SSC CGL` + `IBPS PO` in the UI, both quiz drafts receive those same taxonomy links.

## Validation

Before any MongoDB write, the complete upload is validated for:

- at least one selected category
- at least one selected subcategory
- subcategory ownership under a selected category
- quiz title
- duplicate titles inside the same upload
- questions
- options
- correct answers
- duration
- passing percentage
- maximum attempts

`correct_answer` supports zero-based indexes, letters such as `A/B/C/D`, numeric strings, and exact option text.

All imported quizzes remain drafts until reviewed and published through the existing admin quiz workflow.

## Admin UI

The Bulk Content Studio uses the same taxonomy picker as Course creation:

- all active categories are visible
- multiple categories can be selected
- selecting a category reveals its subcategories
- multiple subcategories can be selected
- the selected taxonomy is sent separately from the JSON file
