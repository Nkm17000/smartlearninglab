from pydantic import BaseModel

class QuestionOption(BaseModel):
    id: str
    text: str

class QuestionCreate(BaseModel):
    quiz_id: str
    question: str
    question_type: str = "MCQ"
    options: list[QuestionOption]
    correct_answer: str
    explanation: str = ""
    difficulty: str = "EASY"
    points: int = 1
