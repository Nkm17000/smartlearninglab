from pydantic import BaseModel

class QuizCreate(BaseModel):
    course_id: str
    lesson_id: str
    title: str
    description: str = ""
    total_questions: int = 0
    passing_score: int = 60
    time_limit_seconds: int = 600
    is_published: bool = True
