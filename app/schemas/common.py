from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "student"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    exam_id: Optional[str] = None
    subject_id: Optional[str] = None
    topic_id: Optional[str] = None
    course_id: Optional[str] = None
    content: Optional[str] = None
    order: int = 0
    is_published: bool = True

class QuestionCreate(BaseModel):
    exam_id: Optional[str] = None
    subject_id: Optional[str] = None
    topic_id: Optional[str] = None
    question: str
    options: list[str]
    answer: int
    explanation: Optional[str] = None
    difficulty: str = "medium"
    is_published: bool = True

class TestSubmit(BaseModel):
    answers: dict[str, int]
