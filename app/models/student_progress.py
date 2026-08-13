from typing import List
from pydantic import BaseModel

class StudentProgressModel(BaseModel):
    user_id: str
    course_id: str
    completed_lessons: List[str] = []
    current_lesson_id: str | None = None
    completed_lessons_count: int = 0
    total_lessons: int = 0
    progress_percentage: float = 0
