# Smart Learning Lab - Bulk Quiz Question Skip Fix

This release is based on the latest uploaded backend repository.

## Bulk quiz behavior

The batch endpoint processes up to 50 quizzes per request.

Question-level errors no longer fail the entire quiz. The importer skips the bad question and continues with the remaining questions.

Skipped question cases include:
- duplicate question within the same quiz
- duplicate question already present in the database
- invalid question object
- empty question text
- wrong number of options
- empty options
- duplicate options
- invalid correct_answer
- invalid marks / negative_marks

If all questions in a quiz are skipped, the quiz itself is skipped and no empty quiz is created.

The response includes:
- created_count
- skipped_count (quizzes)
- failed_count (quizzes)
- skipped_question_count
- skipped_questions details

## Supported quiz JSON

### Single language

```json
{
  "title": "English Grammar - Noun - Set 1",
  "subject": "English",
  "topic": "Noun",
  "questions": [
    {
      "question": "Which is a proper noun?",
      "options": ["city", "country", "Delhi", "river"],
      "correct_answer": 2
    }
  ]
}
```

### Bilingual

```json
{
  "title": "General Science - Motion - Set 1",
  "subject": "General Science",
  "topic": "Motion",
  "questions": [
    {
      "question": {
        "english": "What is acceleration?",
        "hindi": "त्वरण क्या है?"
      },
      "options": {
        "english": ["Change in velocity", "Distance", "Mass", "Time"],
        "hindi": ["वेग में परिवर्तन", "दूरी", "द्रव्यमान", "समय"]
      },
      "correct_answer": 0
    }
  ]
}
```

### Legacy bilingual

```json
{
  "question": "What is acceleration?",
  "question_hindi": "त्वरण क्या है?",
  "options": ["Change in velocity", "Distance", "Mass", "Time"],
  "options_hindi": ["वेग में परिवर्तन", "दूरी", "द्रव्यमान", "समय"],
  "correct_answer": 0
}
```
