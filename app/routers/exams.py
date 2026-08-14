from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from app.db.mongo import get_db
from app.core.security import get_current_user
from app.services.query import paginated
from app.utils import now_utc, oid, serialize_doc

router = APIRouter(prefix="/exams", tags=["Exams"])


@router.get("")
def list_exams(
    category_id: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = {"active": {"$ne": False}}
    if category_id:
        query["categoryId"] = category_id
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"code": {"$regex": search, "$options": "i"}},
        ]
    return paginated(get_db().exams, query, page, limit, [("name", 1)])


@router.get("/{exam_id}")
def get_exam(exam_id: str):
    try:
        doc = get_db().exams.find_one({"_id": oid(exam_id)})
    except ValueError:
        raise HTTPException(400, "Invalid exam id")
    if not doc:
        raise HTTPException(404, "Exam not found")
    return serialize_doc(doc)


@router.get("/{exam_id}/subjects")
def exam_subjects(exam_id: str):
    db = get_db()
    items = list(db.exam_subjects.find({"examId": exam_id}).sort("order", 1))
    # If exam_subjects is not populated, fall back to subjects carrying examIds.
    if not items:
        items = list(db.subjects.find({"examIds": exam_id}).sort("order", 1))
    return [serialize_doc(x) for x in items]


@router.get("/{exam_id}/syllabus")
def exam_syllabus(exam_id: str):
    db = get_db()
    items = list(db.exam_syllabi.find({"examId": exam_id}).sort("order", 1))
    return [serialize_doc(x) for x in items]


@router.get("/{exam_id}/notifications")
def exam_notifications(exam_id: str, limit: int = Query(20, ge=1, le=100)):
    db = get_db()
    items = list(
        db.exam_notifications.find({"examId": exam_id})
        .sort("createdAt", -1)
        .limit(limit)
    )
    return [serialize_doc(x) for x in items]


class ExamProfileRequest(BaseModel):
    targetScore: float | None = Field(default=None, ge=0)
    examDate: str | None = None
    studyMinutesPerDay: int | None = Field(default=None, ge=1, le=1440)
    preparationLevel: str | None = None
    isPrimary: bool = False


@router.get("/me/profiles")
def my_exam_profiles(current_user=Depends(get_current_user)):
    db = get_db()
    items = list(db.user_exam_profiles.find({"userId": current_user["id"]}).sort("isPrimary", -1))
    return [serialize_doc(x) for x in items]


@router.post("/{exam_id}/profile")
def save_exam_profile(exam_id: str, payload: ExamProfileRequest, current_user=Depends(get_current_user)):
    db = get_db()
    exam = None
    if len(exam_id) == 24:
        try:
            exam = db.exams.find_one({"_id": oid(exam_id)})
        except ValueError:
            exam = None
    if exam is None:
        exam = db.exams.find_one({"code": exam_id})
    if exam is None:
        raise HTTPException(404, "Exam not found")

    now = now_utc()
    data = payload.model_dump()
    data.update({"userId": current_user["id"], "examId": exam_id, "updatedAt": now})
    db.user_exam_profiles.update_one(
        {"userId": current_user["id"], "examId": exam_id},
        {"$set": data, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )
    return serialize_doc(db.user_exam_profiles.find_one({"userId": current_user["id"], "examId": exam_id}))
