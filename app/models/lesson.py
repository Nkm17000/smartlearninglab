from pydantic import BaseModel

class LessonModel(BaseModel):
    course_id: str
    subject_id: str
    title: str
    description: str = ""
    lesson_type: str = "VIDEO"
    display_order: int = 1
    duration_minutes: int = 0
    is_free: bool = False
    is_published: bool = True
