from pydantic import BaseModel

class BookmarkModel(BaseModel):
    user_id: str
    resource_type: str
    resource_id: str
