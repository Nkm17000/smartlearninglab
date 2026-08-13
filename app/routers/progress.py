from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
from app.database import student_progress_collection, lessons_collection
from app.schemas.student_progress import ProgressUpdate
from app.utils.helpers import serialize_document

router = APIRouter()

@router.get("/{course_id}")
def get_progress(course_id: str, current_user=Depends(get_current_user)):
    from app.utils.helpers import object_id
    doc = student_progress_collection.find_one({
        "user_id": current_user["_id"],
        "course_id": object_id(course_id)
    })
    return {"status": "success", "data": serialize_document(doc)}

@router.post("/{course_id}/lessons")
def update_progress(course_id: str, request: ProgressUpdate, current_user=Depends(get_current_user)):
    from app.utils.helpers import object_id
    course_oid = object_id(course_id)
    lesson_oid = object_id(request.lesson_id)
    total = lessons_collection.count_documents({"course_id": course_oid})
    progress = student_progress_collection.find_one({
        "user_id": current_user["_id"], "course_id": course_oid
    }) or {
        "user_id": current_user["_id"],
        "course_id": course_oid,
        "completed_lessons": [],
        "completed_lessons_count": 0,
        "total_lessons": total,
        "progress_percentage": 0
    }
    completed = set(progress.get("completed_lessons", []))
    if request.completed:
        completed.add(lesson_oid)
    else:
        completed.discard(lesson_oid)
    progress["completed_lessons"] = list(completed)
    progress["completed_lessons_count"] = len(completed)
    progress["total_lessons"] = total
    progress["progress_percentage"] = round((len(completed) / total) * 100, 2) if total else 0
    student_progress_collection.update_one(
        {"user_id": current_user["_id"], "course_id": course_oid},
        {"$set": progress},
        upsert=True
    )
    return {"status": "success", "data": serialize_document(progress)}
