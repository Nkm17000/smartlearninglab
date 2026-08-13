from pydantic import BaseModel

class BookmarkCreate(BaseModel):
    resource_type: str
    resource_id: str
