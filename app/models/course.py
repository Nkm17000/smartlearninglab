from typing import Optional
from pydantic import BaseModel

class CourseModel(BaseModel):
    title: str
    description: str
    category: str
    level: str
    thumbnail: Optional[str] = None
    rating: float = 0
    total_lessons: int = 0
    estimated_duration_minutes: int = 0
    is_published: bool = True
