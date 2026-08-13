from pydantic import BaseModel

class ProgressUpdate(BaseModel):
    lesson_id: str
    completed: bool = True
