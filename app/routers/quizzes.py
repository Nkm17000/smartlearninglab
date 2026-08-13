from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
from app.database import quizzes_collection, questions_collection, quiz_attempts_collection
from app.schemas.quiz_attempt import QuizSubmitRequest
from app.utils.helpers import object_id, serialize_document

router = APIRouter()

@router.get("/{quiz_id}")
def get_quiz(quiz_id: str):
    quiz = quizzes_collection.find_one({"_id": object_id(quiz_id)})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    questions = []
    for q in questions_collection.find({"quiz_id": object_id(quiz_id)}):
        item = serialize_document(q)
        item.pop("correct_answer", None)
        questions.append(item)
    return {"status": "success", "data": {"quiz": serialize_document(quiz), "questions": questions}}

@router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: str, request: QuizSubmitRequest, current_user=Depends(get_current_user)):
    quiz_oid = object_id(quiz_id)
    correct = 0
    results = []
    for answer in request.answers:
        question = questions_collection.find_one({"_id": object_id(answer.question_id), "quiz_id": quiz_oid})
        if not question:
            continue
        is_correct = answer.selected_answer == question["correct_answer"]
        correct += int(is_correct)
        results.append({
            "question_id": answer.question_id,
            "selected_answer": answer.selected_answer,
            "is_correct": is_correct
        })
    total = len(results)
    score = round((correct / total) * 100, 2) if total else 0
    passed = score >= quizzes_collection.find_one({"_id": quiz_oid}).get("passing_score", 60)
    attempt = {
        "user_id": current_user["_id"],
        "quiz_id": quiz_oid,
        "answers": results,
        "total_questions": total,
        "correct_answers": correct,
        "wrong_answers": total - correct,
        "score": score,
        "passed": passed
    }
    result = quiz_attempts_collection.insert_one(attempt)
    attempt["_id"] = result.inserted_id
    return {"status": "success", "data": serialize_document(attempt)}
