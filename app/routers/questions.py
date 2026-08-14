from fastapi import APIRouter, Query, HTTPException, Depends
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.services.query import paginated
from app.utils import serialize_doc

router = APIRouter(prefix="/questions", tags=["Questions"])


def build_question_query(exam_id=None, subject_id=None, topic_id=None, difficulty=None, qtype=None, search=None):
    query = {"status": {"$ne": "deleted"}}
    if exam_id:
        query["examIds"] = exam_id
    if subject_id:
        query["subjectId"] = subject_id
    if topic_id:
        query["topicId"] = topic_id
    if difficulty:
        query["difficulty"] = difficulty
    if qtype:
        query["type"] = qtype
    if search:
        query["question"] = {"$regex": search, "$options": "i"}
    return query


@router.get("")
def list_questions(
    exam_id: str | None = None,
    subject_id: str | None = None,
    topic_id: str | None = None,
    difficulty: str | None = None,
    qtype: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = build_question_query(exam_id, subject_id, topic_id, difficulty, qtype, search)
    # Never expose answer/explanation in the normal question listing.
    projection = {"correctAnswer": 0, "answer": 0, "explanation": 0, "question_explanations": 0}
    return paginated(get_db().questions, query, page, limit, [("createdAt", -1)], projection)


@router.get("/{question_id}")
def get_question(question_id: str):
    from bson import ObjectId
    db = get_db()
    try:
        doc = db.questions.find_one(
            {"_id": ObjectId(question_id)},
            {"correctAnswer": 0, "answer": 0},
        )
    except Exception:
        doc = None
    if not doc:
        raise HTTPException(404, "Question not found")
    return serialize_doc(doc)


@router.get("/{question_id}/explanation")
def explanation(question_id: str):
    db = get_db()
    doc = db.question_explanations.find_one({"questionId": question_id})
    if not doc:
        # Support explanation embedded in question.
        from bson import ObjectId
        try:
            q = db.questions.find_one({"_id": ObjectId(question_id)})
        except Exception:
            q = None
        if not q:
            raise HTTPException(404, "Question not found")
        return {"questionId": question_id, "explanation": q.get("explanation"), "shortcut": q.get("shortcut")}
    return serialize_doc(doc)


@router.post("/{question_id}/bookmark")
def bookmark_question(question_id: str, current_user=Depends(get_current_user)):
    db = get_db()
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.bookmarks.update_one(
        {"userId": current_user["id"], "entityType": "question", "entityId": question_id},
        {"$set": {"updatedAt": now}, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return {"message": "Question bookmarked"}


@router.delete("/{question_id}/bookmark")
def remove_bookmark(question_id: str, current_user=Depends(get_current_user)):
    get_db().bookmarks.delete_one({"userId": current_user["id"], "entityType": "question", "entityId": question_id})
    return {"message": "Bookmark removed"}
