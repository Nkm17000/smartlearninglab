# Final Quiz Admin Update (V4)

Changes made against the uploaded V4 backend:
- Added POST /api/v1/admin/quizzes/publish-all.
- Added POST /api/v1/admin/quizzes/manual.
- Publish-all validates question_ids and publishes attached questions with the quiz.
- Manual quiz requires exactly 10 MCQs and exactly 4 non-empty options per question.
- Manual quiz remains draft until explicitly published.
- Manual quiz now uses the admin taxonomy selector: multiple categories and multiple subcategories.
- Subcategory choices are shown only under selected categories.
- Category/subcategory IDs are resolved by the existing taxonomy service.

No MongoDB collection migration is required.

Validation:
- Python compileall: PASS
- api.js node --check: PASS
- Source-level verification: Publish All and Manual Quiz routes/buttons/navigation/API are present.
- A full Expo/Metro build was not run because node_modules is not included in the uploaded project and network installation is not assumed.
