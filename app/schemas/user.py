from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    profile_image: str | None = None
    is_active: bool = True
