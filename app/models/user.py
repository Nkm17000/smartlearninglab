from typing import Optional
from pydantic import BaseModel, EmailStr

class UserModel(BaseModel):
    name: str
    email: EmailStr
    role: str = "STUDENT"
    profile_image: Optional[str] = None
    is_active: bool = True
