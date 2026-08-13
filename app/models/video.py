from pydantic import BaseModel

class VideoModel(BaseModel):
    lesson_id: str
    title: str
    storage_provider: str = "AWS_S3"
    storage_key: str
    duration_seconds: int = 0
    thumbnail_key: str = ""
    is_active: bool = True
