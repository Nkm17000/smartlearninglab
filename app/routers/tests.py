from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db.mongo import get_db
from app.core.security import get_current_user
from app.services.query import paginated
from app.utils import serialize_doc

router = APIRouter(prefix="/tests", tags=["Tests"])


@router.get("/mock")
def list_mocks(exam_id: str | None = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    query = {"active": {"$ne": False}}
    if exam_id:
        query["examId"] = exam_id
    return paginated(get_db().mock_tests, query, page, limit, [("createdAt", -1)])


@router.get("/mock/{mock_id}")
def get_mock(mock_id: str):
    db = get_db()
    try:
        mock = db.mock_tests.find_one({"_id": ObjectId(mock_id)})
    except Exception:
        mock = None
    if not mock:
        raise HTTPException(404, "Mock test not found")
    sections = list(db.mock_test_sections.find({"mockTestId": mock_id}).sort("order", 1))
    questions = list(db.mock_test_questions.find({"mockTestId": mock_id}).sort("order", 1))
    result = serialize_doc(mock)
    result["sections"] = [serialize_doc(x) for x in sections]
    # Question answers are deliberately excluded.
    for q in questions:
        q.pop("correctAnswer", None)
        q.pop("answer", None)
    result["questions"] = [serialize_doc(x) for x in questions]
    return result


class StartAttemptRequest(BaseModel):
    mode: str = "mock"


@router.post("/mock/{mock_id}/start")
def start_mock(mock_id: str, payload: StartAttemptRequest | None = None, current_user=Depends(get_current_user)):
    db = get_db()
    try:
        mock = db.mock_tests.find_one({"_id": ObjectId(mock_id)})
    except Exception:
        mock = None
    if not mock:
        raise HTTPException(404, "Mock test not found")

    now = datetime.now(timezone.utc)
    attempt = {
        "userId": current_user["id"],
        "mockTestId": mock_id,
        "mode": payload.mode if payload else "mock",
        "status": "in_progress",
        "startedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    result = db.test_attempts.insert_one(attempt)
    return {"attemptId": str(result.inserted_id), "status": "in_progress", "startedAt": now.isoformat()}


class AnswerRequest(BaseModel):
    questionId: str
    selectedAnswer: str | None = None
    markedForReview: bool = False
    timeSpentSeconds: int = Field(default=0, ge=0)


@router.post("/attempt/{attempt_id}/answer")
def save_answer(attempt_id: str, payload: AnswerRequest, current_user=Depends(get_current_user)):
    db = get_db()
    attempt = db.test_attempts.find_one({"_id": ObjectId(attempt_id), "userId": current_user["id"]})
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    if attempt.get("status") != "in_progress":
        raise HTTPException(409, "Attempt is already submitted")

    now = datetime.now(timezone.utc)
    answer = payload.model_dump()
    answer.update({"attemptId": attempt_id, "userId": current_user["id"], "updatedAt": now, "createdAt": now})
    db.test_attempt_answers.update_one(
        {"attemptId": attempt_id, "questionId": payload.questionId},
        {"$set": answer, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return {"message": "Answer saved"}


@router.post("/attempt/{attempt_id}/submit")
def submit_attempt(attempt_id: str, current_user=Depends(get_current_user)):
    db = get_db()
    attempt = db.test_attempts.find_one({"_id": ObjectId(attempt_id), "userId": current_user["id"]})
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    if attempt.get("status") != "in_progress":
        raise HTTPException(409, "Attempt already submitted")

    mock = db.mock_tests.find_one({"_id": ObjectId(attempt["mockTestId"])})
    answers = list(db.test_attempt_answers.find({"attemptId": attempt_id}))

    score = 0.0
    correct = 0
    wrong = 0
    attempted = 0
    total_questions = len(list(db.mock_test_questions.find({"mockTestId": attempt["mockTestId"]})))

    for ans in answers:
        selected = ans.get("selectedAnswer")
        if selected is None or selected == "":
            continue
        attempted += 1
        try:
            q = db.questions.find_one({"_id": ObjectId(ans["questionId"])})
        except Exception:
            q = None
        if not q:
            q = db.mock_test_questions.find_one({"_id": ObjectId(ans["questionId"])}) if ObjectId.is_valid(ans["questionId"]) else None

        correct_answer = q.get("correctAnswer", q.get("answer")) if q else None
        if correct_answer is not None and str(selected) == str(correct_answer):
            correct += 1
            score += float(q.get("marks", mock.get("marksPerQuestion", 1)) if q else 1)
            is_correct = True
        else:
            wrong += 1
            score -= float(q.get("negativeMarks", mock.get("negativeMarks", 0)) if q else 0)
            is_correct = False
        db.test_attempt_answers.update_one(
            {"_id": ans["_id"]},
            {"$set": {"isCorrect": is_correct}}
        )

    now = datetime.now(timezone.utc)
    result = {
        "attemptId": attempt_id,
        "userId": current_user["id"],
        "mockTestId": attempt["mockTestId"],
        "score": score,
        "correct": correct,
        "wrong": wrong,
        "attempted": attempted,
        "skipped": max(total_questions - attempted, 0),
        "totalQuestions": total_questions,
        "accuracy": round((correct / attempted) * 100, 2) if attempted else 0,
        "submittedAt": now,
    }
    db.test_results.update_one({"attemptId": attempt_id}, {"$set": result}, upsert=True)
    db.test_attempts.update_one({"_id": ObjectId(attempt_id)}, {"$set": {"status": "submitted", "submittedAt": now, "updatedAt": now}})
    return serialize_doc(result)


@router.get("/attempt/{attempt_id}/result")
def attempt_result(attempt_id: str, current_user=Depends(get_current_user)):
    doc = get_db().test_results.find_one({"attemptId": attempt_id, "userId": current_user["id"]})
    if not doc:
        raise HTTPException(404, "Result not found")
    return serialize_doc(doc)


@router.get("/attempts/me")
def my_attempts(current_user=Depends(get_current_user), page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    return paginated(
        get_db().test_attempts,
        {"userId": current_user["id"]},
        page, limit, [("createdAt", -1)]
    )
