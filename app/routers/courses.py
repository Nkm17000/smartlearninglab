from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user, require_admin
from app.schemas.course import CourseCreate
from app.services.course_service import CourseService

router = APIRouter()
service = CourseService()

@router.get("")
def get_courses():
    return {"status": "success", "data": service.get_all({"is_published": True})}

@router.get("/{course_id}")
def get_course(course_id: str):
    result = service.get_by_id(course_id)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"status": "success", "data": result}

@router.post("")
def create_course(request: CourseCreate, current_user=Depends(require_admin)):
    data = request.model_dump()
    data["created_by"] = current_user["_id"]
    return {"status": "success", "data": service.create(data)}
