from pydantic import BaseModel

class NotificationModel(BaseModel):
    user_id: str
    title: str
    message: str
    type: str
    is_read: bool = False
