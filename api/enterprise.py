from fastapi import APIRouter
from typing import Any, Dict
from app.services.enterprise_intelligence import course_health, student_risk, personalized_plan

router = APIRouter(prefix="/api/v1/enterprise", tags=["enterprise-intelligence"])

@router.post("/course-health")
def analyze_course(payload: Dict[str, Any]):
    return course_health(payload)

@router.post("/student-risk")
def analyze_student_risk(payload: Dict[str, Any]):
    return student_risk(payload)

@router.post("/study-plan")
def generate_study_plan(payload: Dict[str, Any]):
    return personalized_plan(payload)
