# Bulk Quiz Fix

The bulk quiz endpoint now accepts flexible quiz categories such as English, Grammar, CAT, Java and Banking. Course categories remain validated separately.

The endpoint is POST /api/v1/admin/bulk/quiz.

correct_answer is zero-based: 0=first option, 1=second, 2=third, 3=fourth.

The backend also validates title, duration, passing percentage, options, duplicate options, correct_answer, marks and difficulty and returns a useful 422 message when input is invalid.
