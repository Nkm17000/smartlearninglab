from pydantic import BaseModel

class SubjectCreate(BaseModel):
    course_id: str
    name: str
    description: str = ""
    display_order: int = 1
    is_published: bool = True
