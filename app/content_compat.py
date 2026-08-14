from app.database import collection

def find_questions(quiz_id):
    rows=list(collection("questions").find({"quiz_id":quiz_id}))
    if not rows:
        rows=list(collection("questions").find({"quizId":quiz_id}))
    return rows
